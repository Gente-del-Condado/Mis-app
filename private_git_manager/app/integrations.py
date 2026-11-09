"""Instala código de integraciones en el montaje de Home Assistant Core."""

import ctypes
import json
import os
import platform
import re
import shutil
import stat
from pathlib import Path
from tempfile import mkdtemp

from .core import Problem, run

DOMAIN = re.compile(r"[a-z][a-z0-9_]{0,79}")
RECEIPT = ".pgm-install.json"


def manifest(folder):
    if not DOMAIN.fullmatch(folder.name) or folder.is_symlink() or not folder.is_dir():
        return None
    path = folder / "manifest.json"
    init = folder / "__init__.py"
    try:
        if any(item.is_symlink() or not item.is_file() for item in (path, init)):
            return None
        with path.open("rb") as stream:
            raw = stream.read(65537)
        if len(raw) > 65536:
            return None
        data = json.loads(raw)
    except (OSError, ValueError, RecursionError):
        return None
    if not isinstance(data, dict) or data.get("domain") != folder.name:
        return None
    for field in ("name", "version"):
        value = data.get(field)
        if not isinstance(value, str) or not value.strip() or len(value) > 200:
            return None
    return {key: data[key] for key in ("domain", "name", "version")}


def catalog(checkout):
    root = checkout / "custom_components"
    if checkout.is_symlink() or root.is_symlink() or not root.is_dir():
        return []
    try:
        return [info for folder in sorted(root.iterdir()) if (info := manifest(folder))]
    except OSError:
        return []


def _rename(old, new, flags):
    # Intercambia ambos directorios sin que Core vea un dominio ausente ni una copia parcial.
    # musl no siempre exporta renameat2; estos son los números ABI de las dos arquitecturas de la app.
    number = {"x86_64": 316, "aarch64": 276}.get(platform.machine())
    if number is None or platform.system() != "Linux":
        raise Problem("La sustitución atómica requiere Linux amd64 o arm64.", "integration_swap")
    syscall = ctypes.CDLL(None, use_errno=True).syscall
    syscall.restype = ctypes.c_long
    result = syscall(
        ctypes.c_long(number),
        ctypes.c_int(-100),
        ctypes.c_char_p(os.fsencode(old)),
        ctypes.c_int(-100),
        ctypes.c_char_p(os.fsencode(new)),
        ctypes.c_uint(flags),
    )
    if result != 0:
        raise Problem(
            "No se pudo intercambiar la integración de forma atómica.", "integration_swap"
        )


class Integrations:
    def __init__(self, manager, config):
        self.manager = manager
        self.config = Path(config)
        self.root = self.config / "custom_components"

    def available(self):
        # El punto de montaje viene del manifiesto de la app, no de una petición HTTP.
        return (
            self.config.is_dir()
            and not self.config.is_symlink()
            and os.access(self.config, os.W_OK)
        )

    def _target(self, domain):
        if not self.available():
            raise Problem(
                "La configuración de Core no está montada con escritura.", "integration_unavailable"
            )
        if not DOMAIN.fullmatch(domain):
            raise Problem("Dominio de integración no válido.", "validation")
        target = self.root / domain
        for path in (self.root, target):
            if path.is_symlink() or (path.exists() and not path.is_dir()):
                raise Problem("La ruta de la integración no es segura.", "integration_conflict")
        return target

    def _source(self, repo_id, domain):
        repo = self.manager.repo(repo_id)
        if not repo.get("commit"):
            raise Problem("Sincroniza primero el repositorio.", "integration_source")
        checkout = self.manager.data / "repos" / repo_id
        source = checkout / "custom_components" / domain
        info = next((item for item in catalog(checkout) if item["domain"] == domain), None)
        if info is None:
            raise Problem("El commit no contiene esa integración.", "integration_source")
        return repo, checkout, source, info

    def summary(self, domain):
        try:
            target = self._target(domain)
            installed = manifest(target)
            return {
                "installed_version": installed["version"] if installed else None,
                "conflict": target.exists() and not installed,
            }
        except Problem:
            return {"installed_version": None, "conflict": True}

    def inspect(self, repo_id, domain):
        target = self._target(domain)
        repo, _, _, info = self._source(repo_id, domain)
        old = manifest(target)
        receipt = target / RECEIPT
        owner = None
        if target.exists():
            if old is None:
                raise Problem(
                    "La carpeta contiene una integración diferente o inválida.",
                    "integration_conflict",
                )
            if receipt.exists() or receipt.is_symlink():
                try:
                    if (
                        receipt.is_symlink()
                        or not receipt.is_file()
                        or receipt.stat().st_size > 1024
                    ):
                        raise ValueError
                    owner = json.loads(receipt.read_bytes())["repo_id"]
                except (OSError, ValueError, TypeError, KeyError) as exc:
                    raise Problem(
                        "El registro de instalación no es válido.", "integration_conflict"
                    ) from exc
                if owner != repo_id:
                    raise Problem(
                        "La integración pertenece a otro repositorio.", "integration_conflict"
                    )
            for directory, dirs, files in os.walk(target):
                for name in dirs + files:
                    mode = (Path(directory) / name).lstat().st_mode
                    if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
                        raise Problem(
                            "La integración local contiene rutas no seguras.",
                            "integration_conflict",
                        )
        return {
            **info,
            "commit": repo["commit"],
            "installed_version": old["version"] if old else None,
            "local_digest": self.manager.tree_digest(target) if old else None,
            "adoption": old is not None and owner is None,
        }

    def deploy(self, repo_id, domain, commit, local_digest, adopt):
        reviewed = self.inspect(repo_id, domain)
        if (
            reviewed["commit"] != commit
            or reviewed["local_digest"] != local_digest
            or reviewed["adoption"] != adopt
        ):
            raise Problem(
                "La integración cambió desde la revisión. Revísala de nuevo.", "integration_changed"
            )
        repo, checkout, source, _ = self._source(repo_id, domain)
        self.manager.verify_checkout(repo, checkout)
        env = self.manager.local_git_env()
        if (
            run(
                [
                    "git",
                    "-C",
                    str(checkout),
                    "ls-files",
                    "--others",
                    "-z",
                    "--",
                    str(source.relative_to(checkout)),
                ],
                env=env,
            )
            or any(
                row.startswith("160000 ")
                for row in run(
                    [
                        "git",
                        "-C",
                        str(checkout),
                        "ls-files",
                        "--stage",
                        "-z",
                        "--",
                        str(source.relative_to(checkout)),
                    ],
                    env=env,
                ).split("\0")
            )
            or (source / RECEIPT).exists()
        ):
            raise Problem(
                "La integración contiene archivos ajenos al commit o reservados.",
                "integration_source",
            )
        target = self._target(domain)
        self.root.mkdir(exist_ok=True)
        holder = Path(mkdtemp(prefix=f".pgm-{domain}-", dir=self.root))
        payload = holder / "previous"
        keep = False
        try:
            self.manager.safe_copy(source, payload)
            (payload / RECEIPT).write_text(json.dumps({"repo_id": repo_id, "commit": commit}))
            if self.inspect(repo_id, domain) != reviewed:
                raise Problem("La integración cambió desde la revisión.", "integration_changed")
            if reviewed["installed_version"] is None:
                _rename(payload, target, 1)  # RENAME_NOREPLACE
            else:
                _rename(target, payload, 2)  # RENAME_EXCHANGE
                keep = True
        finally:
            if not keep:
                shutil.rmtree(holder)
        return {
            "domain": domain,
            "version": reviewed["version"],
            "restart_required": True,
            "previous": str(payload.relative_to(self.config)) if keep else None,
        }
