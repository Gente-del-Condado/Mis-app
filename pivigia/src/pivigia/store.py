"""Persistencia SQLite privada: un proceso por directorio, transacciones y cola durable."""
import os
import json
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from .config import Settings, data_dir
from .server import ServerSettings
from .i18n import tr


class Store:
    def __init__(self, path=None):
        self.path = Path(path) if path else data_dir()
        self.path.mkdir(parents=True, exist_ok=True, mode=0o700)
        # mkdir(mode=...) no corrige instalaciones existentes; cerrar el directorio antes de abrir SQLite.
        self.path.chmod(0o700)
        self.db_path = self.path / "pivigia.sqlite3"
        if self.db_path.exists():
            self.db_path.chmod(0o600)
        with self.db() as db:
            db.executescript("""
              PRAGMA journal_mode=WAL;
              CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY, value TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY, created REAL NOT NULL, updated REAL NOT NULL,
                mailbox TEXT NOT NULL, sender TEXT NOT NULL, raw BLOB,
                status TEXT NOT NULL DEFAULT 'queued', attempts INTEGER NOT NULL DEFAULT 0,
                next_try REAL NOT NULL DEFAULT 0, result TEXT NOT NULL DEFAULT '{}',
                error TEXT NOT NULL DEFAULT '', delivered TEXT NOT NULL DEFAULT '[]');
              CREATE TABLE IF NOT EXISTS camera_events (
                id INTEGER PRIMARY KEY, created REAL NOT NULL, camera_id TEXT NOT NULL,
                camera_name TEXT NOT NULL, kind TEXT NOT NULL, detections TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS recent_detections (
                category TEXT PRIMARY KEY, last_seen REAL NOT NULL);
            """)
            db.execute("INSERT OR IGNORE INTO settings VALUES (1, ?)", (Settings().model_dump_json(),))
            db.execute("UPDATE jobs SET status='queued' WHERE status='processing'")
        os.chmod(self.db_path, 0o600)
        self.token_path = self.path / "admin-token"
        if not self.token_path.exists():
            fd = os.open(self.token_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write(os.environ.get("PIVIGIA_ADMIN_TOKEN") or secrets.token_urlsafe(32))
        self.token_path.chmod(0o600)
        self.token = (os.environ.get("PIVIGIA_ADMIN_TOKEN") or self.token_path.read_text()).strip()
        if len(self.token) < 16:
            raise ValueError(tr("El token de administración debe tener al menos 16 caracteres"))

    @contextmanager
    def db(self):
        connection = sqlite3.connect(self.db_path, timeout=30)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def settings(self):
        with self.db() as db:
            return Settings.model_validate_json(
                db.execute("SELECT value FROM settings WHERE id=1").fetchone()[0]
            )

    def save_settings(self, settings):
        with self.db() as db:
            db.execute("UPDATE settings SET value=? WHERE id=1", (settings.model_dump_json(),))

    def server_settings(self):
        with self.db() as db:
            row = db.execute("SELECT value FROM settings WHERE id=2").fetchone()
        return ServerSettings.model_validate_json(row[0]) if row else ServerSettings()

    def save_server_settings(self, settings):
        with self.db() as db:
            db.execute("INSERT OR REPLACE INTO settings VALUES(2, ?)", (settings.model_dump_json(),))

    def enqueue(self, address, sender, raw, limit):
        """Reserva capacidad y añade el original en la misma transacción de escritura."""
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            count = db.execute("SELECT count(*) FROM jobs WHERE raw IS NOT NULL").fetchone()[0]
            if count >= limit:
                return False
            now = time.time()
            db.execute(
                "INSERT INTO jobs(created,updated,mailbox,sender,raw) VALUES(?,?,?,?,?)",
                (now, now, address, sender, raw),
            )
        return True

    def claim(self):
        """Reclama el trabajo disponible más antiguo sin permitir una doble selección."""
        with self.db() as db:
            db.row_factory = sqlite3.Row
            db.execute("BEGIN IMMEDIATE")
            job = db.execute(
                "SELECT * FROM jobs WHERE status='queued' AND next_try<=? ORDER BY id LIMIT 1", (time.time(),)
            ).fetchone()
            if job:
                db.execute(
                    "UPDATE jobs SET status='processing',updated=? WHERE id=?", (time.time(), job["id"])
                )
                return dict(job)

    def update(self, job_id, **values):
        allowed = {"status", "attempts", "next_try", "result", "error", "raw", "delivered"}
        if not values.keys() <= allowed:
            raise ValueError(tr("Campo no permitido"))
        values["updated"] = time.time()
        with self.db() as db:
            if "result" in values:
                previous = db.execute("SELECT result FROM jobs WHERE id=?", (job_id,)).fetchone()
                result = json.loads(values["result"])
                if previous and json.loads(previous[0]).get("schema") != 2 and result.get("schema") == 2:
                    self._record_detections(db, result.get("detections", []), False, values["updated"])
            db.execute(
                "UPDATE jobs SET " + ",".join(f"{key}=?" for key in values) + " WHERE id=?",
                [*values.values(), job_id],
            )

    def events(self):
        with self.db() as db:
            db.row_factory = sqlite3.Row
            return [
                dict(row)
                for row in db.execute(
                    "SELECT id,created,mailbox,status,attempts,result,error,delivered FROM jobs ORDER BY id DESC LIMIT 100"
                )
            ]

    def stats(self):
        with self.db() as db:
            return dict(db.execute("SELECT status,count(*) FROM jobs GROUP BY status"))

    @staticmethod
    def _record_detections(db, detections, motion, now):
        categories = {d.get("category") for d in detections} & {"person", "car", "animal"}
        if motion:
            categories.add("motion")
        for category in categories:
            db.execute("INSERT INTO recent_detections(category,last_seen) VALUES(?,?) "
                       "ON CONFLICT(category) DO UPDATE SET last_seen=MAX(last_seen,excluded.last_seen)",
                       (category, now))

    def record_detections(self, detections, motion=False):
        with self.db() as db:
            self._record_detections(db, detections, motion, time.time())

    def detection_status(self):
        now, window = time.time(), 120
        with self.db() as db:
            latest = dict(db.execute("SELECT category,last_seen FROM recent_detections"))
        return {"window_seconds": window, "categories": {
            category: {"last_seen": latest.get(category),
                       "recent": category in latest and 0 <= now - latest[category] < window}
            for category in ("person", "car", "animal", "motion")}}

    def cleanup(self, days):
        with self.db() as db:
            db.execute(
                "DELETE FROM jobs WHERE created < ? AND status NOT IN ('queued','processing')",
                (time.time() - days * 86400,),
            )
            db.execute("DELETE FROM camera_events WHERE created < ?", (time.time() - days * 86400,))
            db.execute("DELETE FROM recent_detections WHERE last_seen < ?", (time.time() - days * 86400,))

    def camera_event(self, camera, kind, detections):
        import json

        with self.db() as db:
            db.execute(
                "INSERT INTO camera_events(created,camera_id,camera_name,kind,detections) VALUES(?,?,?,?,?)",
                (time.time(), camera.id, camera.name, kind, json.dumps(detections)),
            )

    def camera_events(self):
        import json

        with self.db() as db:
            db.row_factory = sqlite3.Row
            rows = db.execute("SELECT * FROM camera_events ORDER BY id DESC LIMIT 100").fetchall()
            return [{**dict(row), "detections": json.loads(row["detections"])} for row in rows]

    def retry(self, job_id):
        with self.db() as db:
            return db.execute(
                "UPDATE jobs SET status='queued',attempts=0,next_try=0,error='' "
                "WHERE id=? AND status='failed' AND raw IS NOT NULL",
                (job_id,),
            ).rowcount
