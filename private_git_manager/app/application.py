"""Private, on-demand app settings and logs. Never persist option values."""

import hashlib
import json
import math
import re

import yaml

from .core import SupervisorUncertain
from .errors import Problem

FIELDS = {
    "options",
    "boot",
    "auto_update",
    "network",
    "audio_input",
    "audio_output",
    "ingress_panel",
    "watchdog",
}


class ConfigLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        pairs = self.construct_pairs(node, deep=deep)
        result = {}
        for key, value in pairs:
            if not isinstance(key, str) or key in result:
                raise Problem("Usa claves de texto únicas en el YAML.", "config_yaml")
            result[key] = value
        return result


ConfigLoader.add_constructor(
    "!secret", lambda loader, node: "!secret " + loader.construct_scalar(node)
)


def parse_configuration(source):
    try:
        data = yaml.load(source, Loader=ConfigLoader)
        count = 0

        def check(value, ancestors=(), depth=0):
            nonlocal count
            count += 1
            if count > 5000 or depth > 20 or id(value) in ancestors:
                raise ValueError()
            if isinstance(value, dict):
                if any(not isinstance(k, str) for k in value):
                    raise ValueError()
                for child in value.values():
                    check(child, (*ancestors, id(value)), depth + 1)
            elif isinstance(value, list):
                for child in value:
                    check(child, (*ancestors, id(value)), depth + 1)
            elif value is not None and type(value) not in {str, int, float, bool}:
                raise ValueError()
            elif isinstance(value, float) and not math.isfinite(value):
                raise ValueError()

        check(data)
        if not isinstance(data, dict) or not data or set(data) - FIELDS:
            raise ValueError()
        if "options" in data and not isinstance(data["options"], dict):
            raise ValueError()
        if "boot" in data and data["boot"] not in {"auto", "manual"}:
            raise ValueError()
        for key in ("watchdog", "auto_update", "ingress_panel"):
            if key in data and type(data[key]) is not bool:
                raise ValueError()
        for key in ("audio_input", "audio_output"):
            if data.get(key) is not None and not isinstance(data[key], str):
                raise ValueError()
        if data.get("network") is not None:
            if not isinstance(data["network"], dict):
                raise ValueError()
            for port, value in data["network"].items():
                if not port or len(port) > 80:
                    raise ValueError()
                if value is None:
                    continue
                if type(value) is int and 1 <= value <= 65535:
                    continue
                if (
                    isinstance(value, str)
                    and 0 < len(value) <= 128
                    and not any(ord(c) < 32 for c in value)
                ):
                    continue
                raise ValueError()
        json.dumps(data, allow_nan=False)
        return data
    except (yaml.YAMLError, ValueError, TypeError, RecursionError, OverflowError) as exc:
        # YAML parser diagnostics include source snippets and may echo passwords.
        raise Problem(
            "Revisa el YAML, sus tipos y las claves de configuración permitidas.", "config_yaml"
        ) from exc


def editable(info):
    result = {key: info[key] for key in FIELDS if key in info}
    result.setdefault("options", {})
    if info.get("boot_config") == "manual_only":
        result.pop("boot", None)
    if info.get("host_network"):
        result.pop("network", None)
    return result


def revision(info):
    return hashlib.sha256(
        json.dumps(editable(info), sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


class Applications:
    def __init__(self, manager):
        self.manager = manager

    def info(self, repo_id, slug, mutate=False):
        state = self.manager.snapshot()
        repo = state["repos"].get(repo_id)
        if (
            not repo
            or not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{0,79}", slug)
            or slug == "private_git_manager"
        ):
            raise Problem("Aplicación no encontrada en este repositorio.", "app_missing")
        owner = state["deployments"].get(slug)
        if owner and owner["repo_id"] != repo_id:
            raise Problem("Otra fuente gestiona una aplicación con este slug.", "slug_owned")
        if not owner:
            if not any(app["slug"] == slug for app in repo.get("apps", [])):
                raise Problem("Aplicación no encontrada.", "app_missing")
            target = self.manager.addons / slug
            if target.is_symlink() or not target.is_dir():
                raise Problem("La carpeta local no es segura.", "unsafe_local_folder")
            local = self.manager.discover(target, local=True)
            if len(local) != 1 or local[0]["path"] != "." or local[0]["slug"] != slug:
                raise Problem("No se puede verificar la carpeta local.", "local_manifest_mismatch")
        if mutate and slug in state["transactions"]:
            raise Problem("Revisa primero la recuperación pendiente.", "recovery_required")
        if not self.manager.installed_info(slug):
            raise Problem("Instala primero esta aplicación.", "app_not_installed")
        return self.manager.supervisor.call("GET", f"/addons/local_{slug}/info")

    def configuration(self, repo_id, slug):
        info = self.info(repo_id, slug)
        return {
            "yaml": yaml.safe_dump(editable(info), allow_unicode=True, sort_keys=True),
            "revision": revision(info),
            "schema": info.get("schema"),
            "state": info.get("state"),
            "name": info.get("name", slug),
        }

    def validate(self, repo_id, slug, source):
        self.info(repo_id, slug, mutate=True)
        data = parse_configuration(source)
        if "options" in data:
            result = self.manager.supervisor.call(
                "POST", f"/addons/local_{slug}/options/validate", data["options"]
            )
            if not result.get("valid", False):
                # Supervisor humanize_error can embed submitted secrets: expose no raw message.
                raise Problem(
                    "Las opciones no cumplen el esquema o la comprobación de contraseñas del Supervisor.",
                    "config_invalid",
                )
        return data

    def save(self, repo_id, slug, source, expected_revision, restart=False):
        self.manager.progress("validating")
        info = self.info(repo_id, slug, mutate=True)
        if revision(info) != expected_revision:
            raise Problem(
                "La configuración ha cambiado. Vuelve a abrirla antes de guardar.", "config_changed"
            )
        data = self.validate(repo_id, slug, source)
        # Validate may take time. Check again before applying changes from an old editor.
        current = self.info(repo_id, slug, mutate=True)
        if revision(current) != expected_revision:
            raise Problem(
                "La configuración ha cambiado. Vuelve a abrirla antes de guardar.", "config_changed"
            )
        self.manager.progress("saving_config")
        try:
            self.manager.supervisor.call("POST", f"/addons/local_{slug}/options", data)
        except SupervisorUncertain as exc:
            raise Problem(
                "No se pudo confirmar el guardado. Vuelve a abrir la configuración para comprobarla.",
                "config_uncertain",
            ) from exc
        self.manager.event("app_configured", repo_id=repo_id, slug=slug)
        if restart and current.get("state") == "started":
            self.manager.progress("restarting")
            try:
                self.manager.supervisor.call("POST", f"/addons/local_{slug}/restart")
            except Problem as exc:
                raise Problem(
                    "Configuración guardada; no se pudo confirmar el reinicio. Consulta los logs.",
                    "config_restart_failed",
                ) from exc
        return {"ok": True}

    def logs(self, repo_id, slug):
        info = self.info(repo_id, slug)
        text, truncated = self.manager.supervisor.logs(f"/addons/local_{slug}/logs")
        if truncated:
            text = text.rsplit("\n", 1)[0] if "\n" in text else ""
        # Strip terminal escapes and control characters. Browser also uses textContent exclusively.
        text = re.sub(r"\x1b\][^\x07]*(?:\x07|\x1b\\)|\x1b\[[0-?]*[ -/]*[@-~]", "", text)
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
        secrets = []

        def collect(value, sensitive=False):
            if isinstance(value, dict):
                for key, child in value.items():
                    collect(
                        child,
                        sensitive
                        or bool(
                            re.search(
                                r"password|passwd|token|secret|api.?key|private.?key|credential",
                                key,
                                re.I,
                            )
                        ),
                    )
            elif isinstance(value, list):
                for child in value:
                    collect(child, sensitive)
            elif (
                sensitive and isinstance(value, str) and value and not value.startswith("!secret ")
            ):
                secrets.append(value)

        collect(info.get("options", {}))
        for secret in sorted(set(secrets), key=len, reverse=True):
            text = text.replace(secret, "[REDACTED]")
        # Do not use Manager.redact: it truncates diagnostic messages to 4000 characters.
        for repo in list(self.manager.state["repos"].values()):
            if repo.get("token"):
                text = text.replace(repo["token"], "[REDACTED]")
        text = re.sub(
            r"(?i)(authorization|password|token)(\s*[:=]\s*)(?:Bearer\s+)?[^\s,;]+",
            r"\1\2[REDACTED]",
            text,
        )
        return {"text": text, "truncated": truncated}
