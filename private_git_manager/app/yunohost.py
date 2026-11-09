"""Prepara un paquete Git privado para la API de administración de YunoHost."""

import re
import shutil
import time
import tomllib
import uuid

from .core import Problem, run

STAGE_ID = re.compile(r"[a-f0-9]{32}")
PACKAGE_ID = re.compile(r"[a-z0-9](?:[a-z0-9-]|_(?!_)){0,62}")
MANIFEST_LIMIT = 128 * 1024
STAGE_TTL = 24 * 60 * 60
MAX_STAGES = 8


def package(root):
    path = root / "manifest.toml"
    try:
        if root.is_symlink() or path.is_symlink() or not path.is_file():
            return None
        with path.open("rb") as stream:
            data = stream.read(MANIFEST_LIMIT + 1)
        if len(data) > MANIFEST_LIMIT:
            return None
        manifest = tomllib.loads(data.decode("utf-8"))
    except (OSError, ValueError, RecursionError):
        return None
    if manifest.get("packaging_format") != 2:
        return None
    app_id, name, version = (manifest.get(key) for key in ("id", "name", "version"))
    if not (
        isinstance(app_id, str)
        and PACKAGE_ID.fullmatch(app_id)
        and isinstance(name, str)
        and 0 < len(name.strip()) <= 200
        and isinstance(version, str)
        and 0 < len(version.strip()) <= 100
    ):
        return None
    scripts = root / "scripts"
    if scripts.is_symlink() or any(
        script.is_symlink() or not script.is_file()
        for script in (scripts / item for item in ("install", "upgrade", "remove"))
    ):
        return None
    return {"id": app_id, "name": name, "version": version}


def stage(manager, repo_id, expected_commit):
    repo = manager.repo(repo_id)
    if repo.get("commit") != expected_commit:
        raise Problem("El repositorio cambió. Revisa la nueva versión.", "yunohost_source_changed")
    source = manager.data / "repos" / repo_id
    manager.verify_checkout(repo, source)
    env = manager.local_git_env()
    # El paquete preparado contiene solo archivos del commit, sin ignorados ni submódulos.
    if run(["git", "-C", str(source), "ls-files", "--others", "-z"], env=env) or any(
        entry.startswith("160000 ")
        for entry in run(["git", "-C", str(source), "ls-files", "--stage", "-z"], env=env).split(
            "\0"
        )
    ):
        raise Problem("Sincroniza una copia limpia, sin submódulos.", "yunohost_source_changed")
    info = package(source)
    if not info or info["id"] == "privategit":
        raise Problem(
            "Este paquete no se puede gestionar desde el portal.", "yunohost_package_invalid"
        )

    stages = manager.data / "yunohost-packages"
    stages.mkdir(mode=0o700, exist_ok=True)
    active = 0
    for child in stages.iterdir():
        if not STAGE_ID.fullmatch(child.name) or child.is_symlink() or not child.is_dir():
            continue
        if time.time() - child.stat().st_mtime >= STAGE_TTL:
            shutil.rmtree(child)
        else:
            active += 1
    if active >= MAX_STAGES:
        raise Problem("Hay demasiadas operaciones de YunoHost preparadas.", "yunohost_stage_limit")
    holder = stages / uuid.uuid4().hex
    holder.mkdir(mode=0o700)
    target = holder / "package"
    try:
        manager.safe_copy(source, target)
    except Exception:
        shutil.rmtree(holder, ignore_errors=True)
        raise
    return {"id": holder.name, "path": str(target.absolute()), "package": info}


def discard(data, stage_id):
    if not STAGE_ID.fullmatch(stage_id):
        raise Problem("Identificador de paquete no válido.", "validation")
    holder = data / "yunohost-packages" / stage_id
    if holder.is_dir() and not holder.is_symlink():
        shutil.rmtree(holder)
