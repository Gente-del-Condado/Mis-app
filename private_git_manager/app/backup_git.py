"""Transporte SSH de los .tar nativos del Supervisor, compartido por Forgejo y GitHub."""

import hashlib
import json
import re
import subprocess
from contextlib import contextmanager
from datetime import UTC, datetime
from tempfile import TemporaryDirectory, TemporaryFile

from .core import endpoint
from .errors import Problem

CHUNK = 16 * 1024**2
LIMIT = 512 * 1024**2
OID = re.compile(r"(?:[a-f0-9]{40}|[a-f0-9]{64})")
COPY = re.compile(r"[0-9]{8}T[0-9]{6}Z-[A-Za-z0-9_-]{1,64}")


def invalid():
    return Problem("La copia remota no es válida o está incompleta.", "backup_git_invalid")


class BackupGit:
    def __init__(self, manager, repo_id, slug):
        repo = manager.repo(repo_id)
        if endpoint(repo["url"])[0] != "ssh":
            raise Problem("Selecciona un repositorio conectado por SSH.", "backup_git_ssh")
        self.url = repo["url"]
        self.env = manager.git_env(repo)
        self.data = manager.data
        if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{0,79}", slug):
            raise invalid()
        self.prefix = f"refs/tags/pgm-app/{slug}/"

    @contextmanager
    def git(self):
        with TemporaryDirectory(prefix="pgm-app-backup-", dir=self.data) as folder:

            def git(*args, data=None):
                try:
                    return subprocess.run(
                        ["git", "--git-dir", folder, *args],
                        input=data,
                        env=self.env,
                        capture_output=True,
                        check=True,
                        timeout=120 if args[0] == "ls-remote" else 600,
                    ).stdout
                except (OSError, subprocess.SubprocessError):
                    raise Problem(
                        "Falló la transferencia Git. Revisa el acceso SSH, los permisos y el espacio.",
                        "backup_git_failed",
                    ) from None

            git("init", "--bare", "--quiet")
            yield git

    def refs(self, git, pattern):
        for line in git("ls-remote", "--refs", "--tags", self.url, pattern).splitlines():
            oid, _, ref = line.decode("ascii", errors="replace").partition("\t")
            copy = ref.removeprefix(self.prefix)
            if ref.startswith(self.prefix) and COPY.fullmatch(copy) and OID.fullmatch(oid):
                yield copy, oid

    def list(self):
        with self.git() as git:
            refs = sorted(self.refs(git, self.prefix + "*"), reverse=True)
        return [
            {
                "id": copy,
                "commit": oid,
                "date": datetime.strptime(copy[:16], "%Y%m%dT%H%M%SZ")
                .replace(tzinfo=UTC)
                .isoformat(),
            }
            for copy, oid in refs
            if valid_date(copy)
        ]

    def export(self, backup, archive):
        try:
            date = datetime.fromisoformat(backup["date"])
            if date.tzinfo is None:
                date = date.replace(tzinfo=UTC)
        except ValueError:
            raise invalid() from None
        copy = date.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + backup["slug"]
        if not COPY.fullmatch(copy):
            raise invalid()
        ref = self.prefix + copy
        size = archive.seek(0, 2)
        archive.seek(0)
        if not 0 < size <= LIMIT:
            raise Problem("La copia supera el límite de 512 MiB.", "backup_import_size")
        with self.git() as git:
            digest = hashlib.sha256()
            entries = []

            def blob(name, data):
                oid = git("hash-object", "-w", "--stdin", data=data).strip().decode()
                entries.append(f"100644 blob {oid}\t{name}\n")

            for index in range((size + CHUNK - 1) // CHUNK):
                part = archive.read(CHUNK)
                digest.update(part)
                blob(f"part-{index:03}", part)
            blob(
                "backup.json",
                json.dumps(
                    {
                        "format": "pgm-app-backup-v1",
                        "size": size,
                        "sha256": digest.hexdigest(),
                    },
                    sort_keys=True,
                ).encode(),
            )
            tree = git("mktree", data="".join(entries).encode()).strip().decode()
            # La comparación del árbol permite reintentar un envío que terminó sin respuesta.
            commit = (
                git(
                    "-c",
                    "user.name=Private Git Manager",
                    "-c",
                    "user.email=backup@localhost",
                    "commit-tree",
                    tree,
                    "-m",
                    "Copia cifrada de aplicación",
                )
                .strip()
                .decode()
            )
            existing = dict(self.refs(git, ref)).get(copy)
            if existing:
                git("fetch", "--quiet", "--depth=1", "--no-tags", self.url, ref)
                actual = git("rev-parse", "FETCH_HEAD").strip().decode()
                existing_tree = git("rev-parse", "FETCH_HEAD^{tree}").strip().decode()
                if actual == existing and existing_tree == tree:
                    return {"id": copy, "commit": existing}
                raise Problem("Ya existe otra copia con este identificador.", "backup_git_changed")
            git("push", f"--force-with-lease={ref}:", self.url, f"{commit}:{ref}")
        return {"id": copy, "commit": commit}

    @contextmanager
    def read(self, copy, expected):
        if not COPY.fullmatch(copy) or not OID.fullmatch(expected):
            raise invalid()
        with self.git() as git, TemporaryFile(dir=self.data) as archive:
            ref = self.prefix + copy
            if dict(self.refs(git, ref)).get(copy) != expected:
                raise Problem(
                    "La referencia remota cambió. Actualiza el listado.", "backup_git_changed"
                )
            git("fetch", "--quiet", "--depth=1", "--no-tags", self.url, ref)
            if git("rev-parse", "FETCH_HEAD").strip().decode() != expected:
                raise Problem(
                    "La referencia remota cambió. Actualiza el listado.", "backup_git_changed"
                )

            def blob(name, maximum):
                spec = f"{expected}:{name}"
                if int(git("cat-file", "-s", spec)) > maximum:
                    raise invalid()
                return git("cat-file", "blob", spec)

            try:
                info = json.loads(blob("backup.json", 4096))
                size = info["size"]
                if (
                    info["format"] != "pgm-app-backup-v1"
                    or type(size) is not int
                    or not 0 < size <= LIMIT
                ):
                    raise invalid()
            except (ValueError, KeyError, TypeError, RecursionError):
                raise invalid() from None
            digest = hashlib.sha256()
            for index in range((size + CHUNK - 1) // CHUNK):
                length = min(CHUNK, size - index * CHUNK)
                part = blob(f"part-{index:03}", length)
                if len(part) != length:
                    raise invalid()
                archive.write(part)
                digest.update(part)
            if digest.hexdigest() != info.get("sha256"):
                raise invalid()
            archive.seek(0)
            yield archive


def valid_date(copy):
    try:
        datetime.strptime(copy[:16], "%Y%m%dT%H%M%SZ")
    except ValueError:
        return False
    return True
