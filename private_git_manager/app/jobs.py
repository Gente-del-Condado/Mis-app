"""A bounded, persistent background queue. No operation depends on an HTTP connection."""

import hashlib
import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from .backups import Backups
from .core import Problem
from .storage import atomic_json


class Jobs:
    def __init__(self, manager):
        self.manager = manager
        self.path = manager.data / "jobs.json"
        self.lock = threading.RLock()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pgm-job")
        self.items = json.loads(self.path.read_text()) if self.path.exists() else {}
        for item in self.items.values():
            if item["status"] in {"queued", "running"}:
                item.update(
                    status="interrupted",
                    stage="interrupted",
                    finished_at=time.time(),
                    error="La aplicación se reinició durante la operación.",
                    code="interrupted",
                )
        self.save()

    def save(self):
        atomic_json(self.path, self.items)

    def snapshot(self):
        with self.lock:
            return json.loads(json.dumps(self.items))

    def submit(self, kind, resource, callback, idempotency=None):
        with self.lock:
            digest = hashlib.sha256(idempotency.encode()).hexdigest() if idempotency else None
            if digest:
                existing = next(
                    (j for j in self.items.values() if j.get("request") == digest), None
                )
                if existing:
                    if existing["kind"] != kind or existing["resource"] != resource:
                        raise Problem(
                            "El identificador de petición ya se utilizó para otra operación.",
                            "idempotency_conflict",
                        )
                    return dict(existing)
            if any(
                j["resource"] == resource and j["status"] in {"queued", "running"}
                for j in self.items.values()
            ):
                raise Problem("Ya hay una operación pendiente para este recurso.", "busy")
            if sum(j["status"] in {"queued", "running"} for j in self.items.values()) >= 20:
                raise Problem(
                    "La cola de operaciones está llena. Espera a que finalice un trabajo.", "busy"
                )
            item = {
                "id": uuid.uuid4().hex,
                "kind": kind,
                "resource": resource,
                "status": "queued",
                "stage": "queued",
                "created_at": time.time(),
                "request": digest,
            }
            self.items[item["id"]] = item
            completed = [
                key for key, j in self.items.items() if j["status"] not in {"queued", "running"}
            ]
            for key in completed[:-100]:
                del self.items[key]
            self.save()
            self.executor.submit(self.execute, item["id"], callback)
            return dict(item)

    def update(self, job_id, **values):
        with self.lock:
            self.items[job_id].update(values)
            self.save()

    def execute(self, job_id, callback):
        with self.manager.lock:
            self.update(job_id, status="running", stage="starting", started_at=time.time())
            self.manager.progress = lambda stage: self.update(job_id, stage=stage)
            try:
                self.manager.event("job_started", job_id=job_id, kind=self.items[job_id]["kind"])
                result = callback()
                self.update(
                    job_id, status="succeeded", stage="done", result=result, finished_at=time.time()
                )
                self.manager.event("job_done", job_id=job_id)
            except Exception as exc:
                # Never expose arbitrary exception text or tracebacks: they may contain secrets.
                message = (
                    self.manager.redact(str(exc))
                    if isinstance(exc, Problem)
                    else "Error interno. Revisa los registros del gestor y el Supervisor."
                )
                code = getattr(exc, "code", "internal_error")
                self.update(
                    job_id,
                    status="failed",
                    stage="failed",
                    error=message,
                    code=code,
                    finished_at=time.time(),
                )
                self.manager.event(
                    "job_failed", "error", job_id=job_id, error=message, error_code=code
                )
            finally:
                self.manager.progress = lambda stage: None

    def close(self):
        self.executor.shutdown(wait=False, cancel_futures=True)


class Scheduler:
    def __init__(self, manager, jobs):
        self.manager, self.jobs = manager, jobs
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.loop, daemon=True, name="pgm-sync-scheduler")
        self.next_attempt = {}

    def start(self):
        self.thread.start()

    def tick(self, now=None):
        now = time.time() if now is None else now
        for repo in self.manager.snapshot()["repos"].values():
            interval = repo.get("sync_interval", 0)
            due = max(
                repo.get("synced_at", repo.get("created_at", now)) + interval,
                self.next_attempt.get(repo["id"], 0),
            )
            if interval and now >= due:
                try:
                    self.jobs.submit(
                        "sync",
                        "repo:" + repo["id"],
                        lambda repo_id=repo["id"]: self.manager.sync(repo_id),
                    )
                except Problem:
                    pass
                self.next_attempt[repo["id"]] = now + interval

            for slug, schedule in repo.get("backup_schedules", {}).items():
                if not schedule.get("hours") or now < schedule["next_at"]:
                    continue
                try:
                    self.jobs.submit(
                        "backup_scheduled",
                        "repo:" + repo["id"],
                        lambda repo_id=repo["id"], slug=slug: Backups(self.manager).scheduled(
                            repo_id, slug
                        ),
                    )
                except Problem:
                    pass

    def loop(self):
        while not self.stop.wait(15):
            self.tick()

    def close(self):
        self.stop.set()
        if self.thread.is_alive():
            self.thread.join(timeout=2)
