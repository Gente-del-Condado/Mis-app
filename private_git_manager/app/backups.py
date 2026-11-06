"""App-scoped native Supervisor backups. Passwords live only in queued callbacks."""

import math
import re
from datetime import UTC, datetime

from .application import Applications
from .core import SupervisorUncertain
from .errors import Problem


def backup_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value):
        raise Problem("Identificador de copia no válido.", "backup_invalid")
    return value


def metadata(backup):
    location = backup.get("location")
    attributes = backup.get("location_attributes") or {}
    selected = attributes.get(location or ".local", {})
    size = selected.get("size_bytes", backup.get("size_bytes"))
    if not isinstance(size, (int, float)):
        size = backup.get("size", 0) * 1024**2
    if not isinstance(size, (int, float)) or not math.isfinite(size) or size < 0:
        size = 0
    return {
        "slug": backup_id(backup.get("slug")),
        "name": str(backup.get("name", ""))[:200],
        "date": str(backup.get("date", ""))[:80],
        "type": backup.get("type"),
        "size_bytes": size,
        "protected": bool(selected.get("protected", backup.get("protected", False))),
        "location": location,
    }


class Backups:
    def __init__(self, manager):
        self.manager = manager
        self.apps = Applications(manager)

    def list(self, repo_id, slug):
        self.apps.target(repo_id, slug)
        result = []
        for backup in self.manager.supervisor.call("GET", "/backups").get("backups", []):
            content = backup.get("content") or {}
            if "local_" + slug not in content.get("addons", content.get("apps", [])):
                continue
            if backup.get("location") == ".cloud_backup":
                continue  # Supervisor restricts this location to Home Assistant Core.
            result.append(metadata(backup))
        result.sort(key=lambda item: item["date"], reverse=True)
        return {"backups": result, "installed": bool(self.manager.installed_info(slug))}

    def details(self, repo_id, slug, selected):
        self.apps.target(repo_id, slug)
        backup = self.manager.supervisor.call("GET", f"/backups/{backup_id(selected)}/info")
        app = next(
            (
                a
                for a in backup.get("addons", backup.get("apps", []))
                if a["slug"] == "local_" + slug
            ),
            None,
        )
        if app is None or backup.get("location") == ".cloud_backup":
            raise Problem(
                "La copia no contiene esta aplicación o no es accesible.", "backup_app_missing"
            )
        return {**metadata(backup), "version": str(app.get("version", ""))[:100]}

    def create(self, repo_id, slug, name="", password=None):
        self.apps.info(repo_id, slug, mutate=True)
        self.manager.progress("backupCreating")
        self.manager.event("app_backup_started", slug=slug)
        payload = {
            "name": name.strip()
            or f"PGM · local_{slug} · {datetime.now(UTC):%Y-%m-%d %H:%M:%S UTC}",
            "addons": ["local_" + slug],
            "folders": [],
            "homeassistant": False,
            "location": None,
            "compressed": True,
            "background": False,
        }
        if password:
            payload["password"] = password
        try:
            result = self.manager.supervisor.call("POST", "/backups/new/partial", payload)
        except SupervisorUncertain as exc:
            self.uncertain(exc)
        try:
            selected = result.get("slug")
            if not selected:
                raise ValueError("No completed backup ID")
            self.details(repo_id, slug, selected)
        except (Problem, ValueError) as exc:
            self.uncertain(exc)
        self.manager.event("app_backup_created", slug=slug, backup=selected)
        return {"ok": True, "backup": selected}

    def restore(self, repo_id, slug, selected, password=None):
        self.apps.target(repo_id, slug, mutate=True)
        backup = self.details(repo_id, slug, selected)
        if backup["protected"] and not password:
            raise Problem("Introduce la contraseña de esta copia.", "backup_password_required")
        self.manager.progress("backupRestoring")
        self.manager.event("app_backup_restore_started", slug=slug, backup=selected)
        payload = {
            "addons": ["local_" + slug],
            "folders": [],
            "homeassistant": False,
            "location": backup["location"],
            "background": False,
        }
        if password:
            payload["password"] = password
        try:
            self.manager.supervisor.call("POST", f"/backups/{selected}/restore/partial", payload)
        except SupervisorUncertain as exc:
            self.uncertain(exc)
        try:
            info = self.apps.info(repo_id, slug)
            if backup["version"] and str(info.get("version")) != backup["version"]:
                raise ValueError("Restored version not confirmed")
        except (Problem, ValueError) as exc:
            self.uncertain(exc)
        self.manager.event("app_backup_restored", slug=slug, backup=selected)
        return {"ok": True, "backup": selected}

    @staticmethod
    def uncertain(exc):
        raise Problem(
            "No se pudo confirmar el resultado de la copia o restauración. Puede seguir en curso. "
            "Actualiza las copias y revisa la aplicación y los registros del Supervisor antes de repetir.",
            "backup_uncertain",
        ) from exc
