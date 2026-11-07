"""App-scoped native Supervisor backups. Passwords live only in queued callbacks."""

import hashlib
import json
import math
import re
import tarfile
import time
import uuid
from datetime import UTC, datetime
from urllib.parse import urlencode

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


def locations(backup):
    result = []
    for value in backup.get("locations") or [backup.get("location")]:
        if value == ".cloud_backup":
            continue
        value = None if value in {"", ".local"} else value
        if value not in result:
            result.append(value)
    return result


def shared(backup):
    content = backup.get("content", backup)
    return bool(
        backup.get("type") == "full"
        or len(content.get("addons", content.get("apps", []))) > 1
        or content.get("homeassistant")
        or content.get("folders")
    )


class BackupTarMember(tarfile.TarInfo):
    @classmethod
    def frombuf(cls, buf, encoding, errors):
        member = super().frombuf(buf, encoding, errors)
        if member.type == tarfile.GNUTYPE_SPARSE or (
            member.type not in tarfile.REGULAR_TYPES and member.size > 65536
        ):
            raise ValueError("Unsupported tar metadata")
        return member


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
            result.append({**metadata(backup), "other_content": shared(backup)})
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
        result = {
            **metadata(backup),
            "version": str(app.get("version", ""))[:100],
            "other_content": shared(backup),
            "locations": locations(backup),
        }
        result["revision"] = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
        return result

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

    def import_archive(self, repo_id, slug, archive):
        self.apps.target(repo_id, slug, mutate=True)
        members = set()
        manifest = None
        try:
            size = archive.seek(0, 2)
            archive.seek(0)
            with tarfile.open(fileobj=archive, mode="r:", tarinfo=BackupTarMember) as tar:
                for member in tar:
                    name = member.name.removeprefix("./")
                    if (
                        member.type not in {tarfile.REGTYPE, tarfile.AREGTYPE}
                        or member.offset_data + member.size > size
                        or not name
                        or "/" in name
                        or name in {".", ".."}
                        or name in members
                        or len(members) >= 4096
                    ):
                        raise ValueError("Invalid archive member")
                    members.add(name)
                    if name in {"backup.json", "snapshot.json"}:
                        if manifest is not None or member.size > 1024 * 1024:
                            raise ValueError("Invalid backup metadata")
                        manifest = json.load(tar.extractfile(member))
            if not isinstance(manifest, dict):
                raise ValueError("Missing backup metadata")
            selected = backup_id(manifest.get("slug"))
            apps = manifest.get("addons", manifest.get("apps", []))
            if not isinstance(apps, list):
                raise ValueError("Invalid app metadata")
        except (OSError, ValueError, tarfile.TarError, RecursionError) as exc:
            raise Problem(
                "Selecciona una copia .tar válida de Home Assistant.", "backup_import_invalid"
            ) from exc
        local = "local_" + slug
        if not any(isinstance(item, dict) and item.get("slug") == local for item in apps) or not (
            {f"{local}.tar", f"{local}.tar.gz"} & members
        ):
            raise Problem("La copia no contiene esta aplicación.", "backup_app_missing")
        existing = self.manager.supervisor.call("GET", "/backups").get("backups", [])
        if any(item["slug"] == selected for item in existing):
            raise Problem("Ya existe una copia con este identificador.", "backup_import_duplicate")
        archive.seek(0)
        result = self.manager.supervisor.backup_upload(archive)
        if result.get("slug") != selected:
            raise Problem(
                "Actualiza el listado para comprobar la importación.", "backup_import_uncertain"
            )
        backup = self.details(repo_id, slug, selected)
        schedule = self.manager.repo(repo_id).get("backup_schedules", {}).get(slug)
        if schedule:
            schedule["copies"] = [item for item in schedule["copies"] if item["slug"] != selected]
        self.manager.event("app_backup_imported", slug=slug, backup=selected)
        return backup

    def configure_schedule(self, repo_id, slug, hours, keep):
        self.apps.target(repo_id, slug, mutate=True)
        schedules = self.manager.repo(repo_id).setdefault("backup_schedules", {})
        schedule = schedules.setdefault(slug, {"copies": []})
        if schedule.get("hours") != hours:
            schedule["next_at"] = time.time() + hours * 3600 if hours else None
        schedule.update(hours=hours, keep=keep)
        self.manager.event("app_backup_schedule_saved", repo_id=repo_id, slug=slug)

    def scheduled(self, repo_id, slug):
        schedule = self.manager.repo(repo_id).get("backup_schedules", {}).get(slug, {})
        now = time.time()
        if not schedule.get("hours") or schedule["next_at"] > now:
            return
        schedule.update(next_at=now + schedule["hours"] * 3600, last_attempt=now)
        self.manager.save()
        name = f"PGM · local_{slug} · {uuid.uuid4().hex}"
        result = self.create(repo_id, slug, name)
        selected = result["backup"]
        detail = self.details(repo_id, slug, selected)
        if detail["name"] != name or detail["other_content"] or detail["type"] != "partial":
            raise Problem("No se pudo verificar la copia programada.", "backup_uncertain")
        schedule["copies"].append({"slug": selected, "name": name, "date": detail["date"]})
        schedule["last_success"] = time.time()
        self.manager.save()
        listed = self.list(repo_id, slug)["backups"]
        present = {item["slug"] for item in listed}
        schedule["copies"] = [item for item in schedule["copies"] if item["slug"] in present]
        self.manager.save()
        for item in schedule["copies"][: -schedule["keep"]]:
            detail = self.details(repo_id, slug, item["slug"])
            if (
                detail["name"] == item["name"]
                and detail["date"] == item["date"]
                and detail["type"] == "partial"
                and not detail["other_content"]
                and None in detail["locations"]
            ):
                self.delete(repo_id, slug, item["slug"], detail["revision"], local_only=True)
            schedule["copies"].remove(item)
            self.manager.save()
        return result

    def reviewed(self, repo_id, slug, selected, expected_revision):
        backup = self.details(repo_id, slug, selected)
        if backup["revision"] != expected_revision:
            raise Problem(
                "La copia cambió. Actualiza el listado y revisa la operación de nuevo.",
                "backup_changed",
            )
        return backup

    def download(self, repo_id, slug, selected, expected_revision):
        backup = self.reviewed(repo_id, slug, selected, expected_revision)
        query = urlencode({"location": backup["location"] or ""})
        stream = self.manager.supervisor.backup_download(
            f"/backups/{backup_id(selected)}/download?{query}"
        )
        try:
            self.manager.event("app_backup_download_started", slug=slug, backup=selected)
        except Exception:
            stream.close()
            raise
        return stream

    def delete(self, repo_id, slug, selected, expected_revision, *, local_only=False):
        self.apps.target(repo_id, slug, mutate=True)
        backup = self.reviewed(repo_id, slug, selected, expected_revision)
        targets = [None] if local_only else backup["locations"]
        self.manager.progress("backupDeleting")
        self.manager.event("app_backup_delete_started", slug=slug, backup=selected)
        try:
            self.manager.supervisor.call(
                "DELETE", f"/backups/{backup_id(selected)}", {"location": targets}
            )
        except SupervisorUncertain as exc:
            self.delete_uncertain(exc)
        try:
            remaining = self.manager.supervisor.call("GET", "/backups").get("backups", [])
            for item in remaining:
                if item.get("slug") == selected and any(
                    value in targets for value in locations(item)
                ):
                    raise ValueError("Backup still present")
        except (Problem, ValueError) as exc:
            self.delete_uncertain(exc)
        self.manager.event("app_backup_deleted", slug=slug, backup=selected)
        return {"ok": True, "backup": selected}

    @staticmethod
    def delete_uncertain(exc):
        raise Problem(
            "No se pudo confirmar el borrado. Puede seguir en curso o haber sido parcial. Actualiza las copias y revisa el Supervisor antes de repetir.",
            "backup_delete_uncertain",
        ) from exc

    @staticmethod
    def uncertain(exc):
        raise Problem(
            "No se pudo confirmar el resultado de la copia o restauración. Puede seguir en curso. "
            "Actualiza las copias y revisa la aplicación y los registros del Supervisor antes de repetir.",
            "backup_uncertain",
        ) from exc
