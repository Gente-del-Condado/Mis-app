"""Crash-safe, private JSON writes used for state, jobs and transaction journals."""

import json
import os
import shutil
import tempfile
import uuid
from pathlib import Path


def atomic_json(path: Path, value):
    temporary = path.with_name("." + path.name + "-" + uuid.uuid4().hex)
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def migrate_app_data(legacy: Path, target: Path):
    """Stage an upgrade on the destination volume and preserve the legacy copy."""
    if target.is_symlink():
        raise RuntimeError("La carpeta de datos del gestor no puede ser un enlace simbólico.")
    if target.exists() or not (legacy / "state.json").is_file():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".pgm-migrate-", dir=target.parent) as temporary:
        staged = Path(temporary) / "data"
        staged.mkdir(mode=0o700)
        for name in (
            "state.json",
            "jobs.json",
            "keys",
            "repos",
            "home",
            "known_hosts",
            "manager.log",
            "manager.log.1",
            "manager.log.2",
            "manager.log.3",
        ):
            source = legacy / name
            destination = staged / name
            if source.is_symlink():
                raise RuntimeError("Ruta inesperada en los datos anteriores del gestor.")
            if source.is_dir():
                shutil.copytree(source, destination, symlinks=True)
            elif source.is_file():
                shutil.copy2(source, destination)
        staged.rename(target)
