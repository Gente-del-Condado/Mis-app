"""Exporta el catálogo del gestor por SSH y aplica importaciones sin reemplazar datos."""

import re
import subprocess
import time
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .core import Problem, endpoint, validate_ref

PREFIX = "refs/tags/pgm-config-"
COPY_ID = re.compile(r"[0-9]{8}T[0-9]{6}Z-[0-9a-f]{32}")
OID = re.compile(r"(?:[a-f0-9]{40}|[a-f0-9]{64})")
RECIPIENT = re.compile(r"age1[a-z0-9]{58}")
IDENTITY = re.compile(r"AGE-SECRET-KEY-1[A-Z0-9]{58}")
MAX_BYTES = 1024**2
FILE = "config.json.age"


class Repository(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str = Field(min_length=1, max_length=80)
    url: str = Field(min_length=1, max_length=2048)
    ref: str = Field(min_length=1, max_length=200)
    username: str = Field(min_length=1, max_length=128)
    fingerprint: str | None = Field(default=None, pattern=r"^SHA256:[A-Za-z0-9+/]{43}$")


class Catalog(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    format: Literal["pgm-catalog-v1"]
    repositories: list[Repository] = Field(max_length=250)


def _command(command, env, data=None, *, error="migration_git"):
    try:
        return subprocess.run(
            command, input=data, env=env, capture_output=True, check=True, timeout=120
        ).stdout
    except (OSError, subprocess.SubprocessError):
        # No propaga stderr ni los datos recibidos por stdin.
        raise Problem("No se pudo completar la operación de migración.", error) from None


class Migration:
    def __init__(self, manager, repo_id):
        self.manager = manager
        repo = manager.repo(repo_id)
        self.url = repo["url"]
        if endpoint(self.url)[0] != "ssh":
            raise Problem("Conecta el destino de recuperación por SSH.", "migration_ssh")
        self.env = manager.git_env(repo)
        self.local_env = manager.local_git_env()

    @contextmanager
    def _git(self):
        with TemporaryDirectory(prefix="pgm-migration-") as folder:

            def git(*args, data=None):
                return _command(["git", "--git-dir", folder, *args], self.env, data)

            git("init", "--bare", "--quiet")
            yield git, Path(folder)

    def _refs(self, git):
        refs = {}
        for line in (
            git("ls-remote", "--refs", "--tags", self.url, PREFIX + "*").decode().splitlines()
        ):
            oid, _, ref = line.partition("\t")
            copy = ref.removeprefix(PREFIX)
            if ref.startswith(PREFIX) and COPY_ID.fullmatch(copy) and OID.fullmatch(oid):
                refs[copy] = oid
        return refs

    def copies(self):
        with self._git() as (git, _):
            return [
                {"id": copy, "commit": oid}
                for copy, oid in sorted(self._refs(git).items(), reverse=True)[:100]
            ]

    def export(self, recipient):
        if not RECIPIENT.fullmatch(recipient):
            raise Problem("Introduce una clave pública age válida.", "migration_recipient")
        repos = []
        for repo in self.manager.state["repos"].values():
            scheme, host, port = endpoint(repo["url"])
            trusted = (
                self.manager.state["hosts"].get(f"{host}:{port}", {}) if scheme == "ssh" else {}
            )
            repos.append(
                {
                    "name": repo["name"],
                    "url": repo["url"],
                    "ref": repo["ref"],
                    "username": repo.get("username") or "git",
                    "fingerprint": trusted.get("fingerprint"),
                }
            )
        try:
            catalog = Catalog(format="pgm-catalog-v1", repositories=repos)
        except ValidationError:
            raise Problem(
                "El catálogo supera los límites de exportación.", "migration_size"
            ) from None
        raw = catalog.model_dump_json().encode()
        if len(raw) > MAX_BYTES - 4096:
            raise Problem("El catálogo supera el límite de exportación.", "migration_size")
        encrypted = _command(
            ["age", "--encrypt", "--recipient", recipient],
            self.local_env,
            raw,
            error="migration_encrypt",
        )
        copy = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex
        ref = PREFIX + copy
        with self._git() as (git, _):
            blob = git("hash-object", "-w", "--stdin", data=encrypted).decode().strip()
            tree = git("mktree", data=f"100644 blob {blob}\t{FILE}\n".encode()).decode().strip()
            commit = (
                git(
                    "-c",
                    "user.name=Private Git Manager",
                    "-c",
                    "user.email=backup@localhost",
                    "commit-tree",
                    tree,
                    "-m",
                    "Copia cifrada de Private Git Manager",
                )
                .decode()
                .strip()
            )
            git("push", f"--force-with-lease={ref}:", self.url, f"{commit}:{ref}")
        return {"id": copy, "commit": commit}

    def read(self, copy, expected, identity):
        if not COPY_ID.fullmatch(copy) or not OID.fullmatch(expected):
            raise Problem("Selecciona una copia válida.", "migration_invalid")
        if not IDENTITY.fullmatch(identity):
            raise Problem("Introduce una clave privada age válida.", "migration_identity")
        with self._git() as (git, folder):
            ref = PREFIX + copy
            git("fetch", "--no-tags", "--depth=1", self.url, ref)
            if git("rev-parse", "FETCH_HEAD").decode().strip() != expected:
                raise Problem("La copia cambió después de seleccionarla.", "migration_changed")
            blob = f"{expected}:{FILE}"
            if (
                git("cat-file", "-t", blob) != b"blob\n"
                or int(git("cat-file", "-s", blob)) > MAX_BYTES
            ):
                raise Problem("La copia no tiene un formato válido.", "migration_invalid")
            ciphertext = folder / FILE
            ciphertext.write_bytes(git("cat-file", "blob", blob))
            # Solo el archivo cifrado se escribe en el disco. La identidad entra por stdin.
            raw = _command(
                ["age", "--decrypt", "--identity", "-", str(ciphertext)],
                self.local_env,
                (identity + "\n").encode(),
                error="migration_decrypt",
            )
        try:
            catalog = Catalog.model_validate_json(raw)
            for repo in catalog.repositories:
                endpoint(repo.url)
                validate_ref(repo.ref)
                if not repo.name.strip() or any(ord(c) < 32 for c in repo.name + repo.username):
                    raise ValueError
        except (ValidationError, ValueError, Problem):
            raise Problem(
                "La configuración descifrada no es válida.", "migration_invalid"
            ) from None
        return catalog

    def apply(self, catalog):
        # Solo añade entradas nuevas. Ni las claves ni los repositorios existentes se reemplazan.
        existing = self.manager.state["repos"]
        repos = dict(existing)
        seen = {(repo["url"], repo["ref"]) for repo in existing.values()}
        for entry in catalog.repositories:
            pair = (entry.url, entry.ref)
            if pair in seen:
                continue
            seen.add(pair)
            repo_id = uuid.uuid4().hex
            repos[repo_id] = {
                "id": repo_id,
                "name": entry.name,
                "url": entry.url,
                "ref": entry.ref,
                "username": entry.username,
                "key_id": None,
                "token": None,
                "commit": None,
                "apps": [],
                "created_at": time.time(),
                "sync_interval": 0,
            }
        if len(repos) != len(existing):
            self.manager.state["repos"] = repos
            try:
                self.manager.save()
            except OSError:
                self.manager.state["repos"] = existing
                raise
        return {"added": len(repos) - len(existing)}
