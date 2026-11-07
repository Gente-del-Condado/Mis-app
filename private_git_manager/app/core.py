"""Persistent Git/SSH operations. All callers hold Manager.lock for mutations."""

import base64
import hashlib
import json
import logging
import os
import re
import shlex
import shutil
import stat
import subprocess
import threading
import time
import uuid
from logging.handlers import RotatingFileHandler
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import yaml

from .documentation import RepositoryDocs
from .errors import Problem
from .messages import event_text
from .storage import atomic_json

VERSION = "0.11.1"


class SupervisorUncertain(Problem):
    """The request may still be running: never assume a timed-out mutation failed."""


class SupervisorRejected(Problem):
    pass


def run(args, *, cwd=None, env=None, timeout=180):
    try:
        result = subprocess.run(
            args, cwd=cwd, env=env, text=True, capture_output=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Problem(f"No se pudo ejecutar {args[0]} o se agotó el tiempo.") from exc
    if result.returncode:
        error = result.stderr.lower()
        classifications = [
            (
                ("host key verification failed", "remote host identification has changed"),
                "La identidad SSH del servidor no coincide. Verifica su huella antes de continuar.",
                "host_key_changed",
            ),
            (
                ("permission denied", "authentication failed", "could not read username"),
                "Autenticación rechazada. Revisa la clave de despliegue o el token y sus permisos de lectura.",
                "credential_error",
            ),
            (
                ("couldn't find remote ref", "remote branch"),
                "La rama o etiqueta no existe en el repositorio remoto.",
                "ref_missing",
            ),
            (
                ("could not resolve", "name or service not known"),
                "No se pudo resolver el nombre del servidor. Revisa DNS y conectividad.",
                "dns_error",
            ),
            (
                ("connection refused", "connection timed out", "network is unreachable"),
                "No se pudo conectar al servidor. Revisa dirección, puerto y red.",
                "connection_refused",
            ),
            (
                ("repository not found", "does not appear to be a git repository"),
                "Repositorio no encontrado o sin permiso de lectura.",
                "repo_access",
            ),
            (
                ("certificate", "ssl peer"),
                "No se pudo verificar el certificado TLS del servidor.",
                "tls_error",
            ),
        ]
        for patterns, message, code in classifications:
            if any(pattern in error for pattern in patterns):
                raise Problem(message, code)
        # Never return raw process output: servers may echo secrets.
        raise Problem(f"{args[0]} falló. Revisa URL, referencia, permisos y confianza SSH.")
    return result.stdout.strip()


def identifier(value):
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", value):
        raise Problem("Identificador no válido.")
    return value


def endpoint(url):
    """Allow SSH and HTTPS only; reject credentials in URLs and option injection."""
    if any(c.isspace() or ord(c) < 32 for c in url) or len(url) > 2048:
        raise Problem("URL no válida.")
    if "://" not in url:
        match = re.fullmatch(r"([a-zA-Z0-9_.-]+)@([a-zA-Z0-9.-]+):([a-zA-Z0-9_./-]+)", url)
        if not match:
            raise Problem("Utiliza ssh://usuario@servidor:puerto/propietario/repo.git o HTTPS.")
        user, host, path = match.groups()
        if user.startswith("-") or not path or path.startswith("-"):
            raise Problem("URL SSH no válida.")
        return "ssh", host.lower(), 22
    try:
        parsed = urlsplit(url)
        port = parsed.port if parsed.port is not None else (22 if parsed.scheme == "ssh" else 443)
    except ValueError as exc:
        raise Problem("Puerto no válido.") from exc
    if parsed.scheme not in {"ssh", "https"} or not parsed.hostname:
        raise Problem("Solo se permiten conexiones SSH o HTTPS.")
    if not re.fullmatch(r"[a-zA-Z0-9.-]+", parsed.hostname) or parsed.hostname.startswith("-"):
        raise Problem("Nombre de servidor no válido (usa un nombre DNS o IPv4).")
    if parsed.password is not None or parsed.query or parsed.fragment:
        raise Problem("No incluyas contraseñas, tokens, consultas ni fragmentos en la URL.")
    if parsed.scheme == "https" and parsed.username is not None:
        raise Problem("Introduce el token en el campo de credenciales, nunca en la URL.")
    if parsed.scheme == "ssh" and (
        not parsed.username
        or not re.fullmatch(r"[a-zA-Z0-9_.-]+", parsed.username)
        or parsed.username.startswith("-")
    ):
        raise Problem("La URL SSH debe incluir un usuario válido.")
    if not 1 <= port <= 65535 or parsed.path in {"", "/"}:
        raise Problem("Falta la ruta del repositorio o el puerto es incorrecto.")
    return parsed.scheme, parsed.hostname.lower(), port


def validate_ref(ref):
    if (
        not re.fullmatch(r"[a-zA-Z0-9_][a-zA-Z0-9_./-]{0,199}", ref)
        or ".." in ref
        or ref.endswith(("/", "."))
    ):
        raise Problem("Rama o etiqueta no válida.")
    return ref


def fingerprint(line):
    parts = line.split()
    if len(parts) != 3 or parts[1] != "ssh-ed25519":
        raise Problem("La clave de host debe ser Ed25519.")
    try:
        raw = base64.b64decode(parts[2], validate=True)
    except ValueError as exc:
        raise Problem("Clave de host no válida.") from exc
    if len(raw) != 51 or raw[:19] != b"\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20":
        raise Problem("Clave de host no válida.")
    return "SHA256:" + base64.b64encode(hashlib.sha256(raw).digest()).decode().rstrip("=")


class Supervisor:
    def __init__(self, transport=None):
        self.token = os.environ.get("SUPERVISOR_TOKEN")
        self.transport = transport

    def call(self, method, path, payload=None):
        if not self.token:
            raise Problem(
                "Supervisor no disponible. El modo local permite Git y detección, pero no instalar.",
                "supervisor_missing",
            )
        try:
            with httpx.Client(
                transport=self.transport,
                trust_env=False,
                timeout=httpx.Timeout(900 if method in {"POST", "DELETE"} else 20, connect=15),
            ) as client:
                response = client.request(
                    method,
                    "http://supervisor" + path,
                    headers={"Authorization": f"Bearer {self.token}"},
                    json=(payload if payload is not None else {})
                    if method in {"POST", "DELETE"}
                    else None,
                )
            if response.status_code >= 500:
                raise SupervisorUncertain(
                    "El Supervisor devolvió un error. La operación podría seguir en curso; comprueba su estado.",
                    "supervisor_uncertain",
                )
            if response.status_code >= 400:
                raise SupervisorRejected(
                    "Supervisor rechazó la operación. Consulta sus registros en Home Assistant.",
                    "supervisor_rejected",
                )
            payload = response.json()
            if payload.get("result") != "ok":
                raise SupervisorRejected(
                    "Supervisor rechazó la operación. Consulta sus registros en Home Assistant.",
                    "supervisor_rejected",
                )
            return payload.get("data", {})
        except SupervisorRejected:
            raise
        except (httpx.HTTPError, ValueError) as exc:
            if method in {"POST", "DELETE"}:
                raise SupervisorUncertain(
                    "La conexión con Supervisor se interrumpió. La operación podría seguir en curso; comprueba su estado.",
                    "supervisor_uncertain",
                ) from exc
            raise Problem("No se pudo consultar el Supervisor.", "supervisor_unavailable") from exc

    def backup_upload(self, archive):
        if not self.token:
            raise Problem("Supervisor no disponible.", "supervisor_missing")
        filename = f"pgm-import-{uuid.uuid4().hex}.tar"
        try:
            with httpx.Client(
                transport=self.transport, trust_env=False, timeout=httpx.Timeout(900, connect=15)
            ) as client:
                response = client.post(
                    "http://supervisor/backups/new/upload",
                    params={"location": ".local", "filename": filename},
                    headers={"Authorization": f"Bearer {self.token}"},
                    files={"file": (filename, archive, "application/x-tar")},
                )
            if response.status_code >= 500:
                raise ValueError("Unconfirmed upload")
            if response.status_code != 200:
                raise SupervisorRejected(
                    "Supervisor rechazó la copia importada.", "backup_import_failed"
                )
            result = response.json()
            if result.get("result") != "ok" or not isinstance(result.get("data"), dict):
                raise SupervisorRejected(
                    "Supervisor rechazó la copia importada.", "backup_import_failed"
                )
            return result["data"]
        except (httpx.HTTPError, ValueError) as exc:
            raise SupervisorUncertain(
                "No se pudo confirmar la importación. Actualiza el listado antes de repetir.",
                "backup_import_uncertain",
            ) from exc

    def backup_download(self, path):
        if not self.token:
            raise Problem("Supervisor no disponible.", "supervisor_missing")
        return BackupDownload(self.token, self.transport, path)

    def logs(self, path):
        if not self.token:
            raise Problem("Supervisor no disponible.", "supervisor_missing")
        limit = 512 * 1024
        try:
            with httpx.Client(transport=self.transport, trust_env=False, timeout=20) as client:
                with client.stream(
                    "GET",
                    "http://supervisor" + path,
                    headers={"Authorization": f"Bearer {self.token}", "Accept": "text/plain"},
                ) as response:
                    if response.status_code >= 400:
                        raise Problem(
                            "No se pudieron leer los logs de la aplicación.", "app_logs_failed"
                        )
                    chunks = bytearray()
                    truncated = False
                    for chunk in response.iter_bytes():
                        room = limit - len(chunks)
                        chunks.extend(chunk[:room])
                        if len(chunk) > room:
                            truncated = True
                            break
                    return chunks.decode("utf-8", errors="replace"), truncated
        except httpx.HTTPError as exc:
            raise Problem(
                "No se pudieron leer los logs de la aplicación.", "app_logs_failed"
            ) from exc


class BackupDownload:
    """One authenticated upstream stream, closed on completion or client cancellation."""

    def __init__(self, token, transport, path):
        self.client = httpx.Client(
            transport=transport, trust_env=False, timeout=httpx.Timeout(120, connect=15)
        )
        self.response = None
        try:
            request = self.client.build_request(
                "GET",
                "http://supervisor" + path,
                headers={"Authorization": f"Bearer {token}", "Accept-Encoding": "identity"},
            )
            self.response = self.client.send(request, stream=True)
            mime = self.response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            if (
                self.response.status_code != 200
                or mime not in {"application/x-tar", "application/tar", "application/octet-stream"}
                or self.response.headers.get("content-encoding", "identity") != "identity"
            ):
                raise ValueError("Invalid backup response")
        except (httpx.HTTPError, ValueError) as exc:
            self.close()
            raise Problem(
                "No se pudo descargar la copia. Actualiza el listado y vuelve a intentarlo.",
                "backup_download_failed",
            ) from exc

    @property
    def headers(self):
        length = self.response.headers.get("content-length", "")
        return {"Content-Length": length} if length.isascii() and length.isdigit() else {}

    def chunks(self):
        try:
            yield from self.response.iter_bytes(chunk_size=64 * 1024)
        except httpx.HTTPError:
            raise Problem(
                "La descarga se interrumpió. Vuelve a descargar la copia completa.",
                "backup_download_failed",
            ) from None
        finally:
            self.close()

    def close(self):
        if self.response is not None:
            self.response.close()
        self.client.close()


class Manager:
    def __init__(self, data, addons, supervisor=None):
        self.data, self.addons = Path(data).absolute(), Path(addons).absolute()
        self.lock = threading.RLock()
        self.supervisor = supervisor or Supervisor()
        for path in (self.data, self.data / "keys", self.data / "repos", self.data / "home"):
            path.mkdir(parents=True, exist_ok=True, mode=0o700)
            path.chmod(0o700)
        self.addons.mkdir(parents=True, exist_ok=True)
        self.state_file = self.data / "state.json"
        self.state = (
            json.loads(self.state_file.read_text())
            if self.state_file.exists()
            else {"keys": {}, "hosts": {}, "repos": {}, "deployments": {}, "events": []}
        )
        if not isinstance(self.state, dict) or not all(
            isinstance(self.state.get(k), dict) for k in ("keys", "hosts", "repos", "deployments")
        ):
            raise RuntimeError(
                "El archivo de estado no es válido. Conserva /data para su recuperación."
            )
        self.recover_checkouts()
        self.state.setdefault("transactions", {})
        self.state.setdefault("settings", {"sync_interval": 0})
        self.progress = lambda stage: None
        self.log_path = self.data / "manager.log"
        self.logger = logging.getLogger("pgm." + str(self.data))
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        if not self.logger.handlers:
            handler = RotatingFileHandler(self.log_path, maxBytes=1024 * 1024, backupCount=3)
            handler.setFormatter(logging.Formatter("%(message)s"))
            self.logger.addHandler(handler)
            console = logging.StreamHandler()
            console.setFormatter(logging.Formatter("%(message)s"))
            self.logger.addHandler(console)
        self.log_path.chmod(0o600)
        for record in self.state["deployments"].values():
            if record.get("status") == "pending":
                record["status"] = "interrupted"
        for repo in self.state["repos"].values():
            checkout = self.data / "repos" / repo["id"]
            if repo.get("commit") and checkout.is_dir():
                try:
                    docs = RepositoryDocs(checkout, repo["id"])
                    repo["apps"] = self.discover(checkout)
                    repo["catalog"] = docs.catalog(repo["apps"])
                    repo["app_digests"] = self.app_digests(checkout, repo["apps"])
                except Problem:
                    pass  # Old checkouts remain usable; a new sync will report invalid metadata.
        self.save()
        self.askpass = self.data / "askpass.sh"
        self.askpass.write_text(
            '#!/bin/sh\ncase "$1" in *Username*) printf "%s" "$PGM_USERNAME";; *) printf "%s" "$PGM_TOKEN";; esac\n'
        )
        self.askpass.chmod(0o700)

    def local_git_env(self):
        return {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(self.data / "home"),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "LC_ALL": "C",
        }

    def checkout_commit(self, root):
        return run(["git", "-C", str(root), "rev-parse", "HEAD"], env=self.local_git_env())

    def recover_checkouts(self):
        for old in (self.data / "repos").glob("*-old"):
            target = old.with_name(old.name[:-4])
            repo = self.state["repos"].get(target.name)
            if not target.exists():
                old.rename(target)
                continue
            try:
                if repo and self.checkout_commit(target) != repo.get("commit"):
                    if self.checkout_commit(old) == repo.get("commit"):
                        shutil.rmtree(target)
                        old.rename(target)
                    else:
                        repo.update(
                            commit=None, apps=[], catalog=None, app_digests={}, sync_changes={}
                        )
                        continue  # Preserve both trees when neither matches known state.
                else:
                    shutil.rmtree(old)
            except Problem:
                if repo:
                    repo.update(commit=None, apps=[], catalog=None, app_digests={}, sync_changes={})

    def verify_checkout(self, repo, root):
        try:
            actual = self.checkout_commit(root)
            dirty = run(
                ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=all"],
                env=self.local_git_env(),
            )
        except Problem as exc:
            raise Problem(
                "La copia de trabajo no es válida. Sincroniza de nuevo el repositorio.",
                "source_changed",
            ) from exc
        if actual != repo["commit"] or dirty:
            raise Problem(
                "El código descargado no coincide con el commit registrado. Sincroniza de nuevo.",
                "source_changed",
            )

    def save(self):
        atomic_json(self.state_file, self.state)
        # Immutable public snapshot: long Git/Supervisor jobs never block UI polling.
        public = json.loads(json.dumps(self.state))
        for repo in public["repos"].values():
            repo["has_token"] = bool(repo.pop("token", ""))
        public["supervisor"] = bool(self.supervisor.token)
        public["version"] = VERSION
        self._public = json.dumps(public, ensure_ascii=False)

    def redact(self, message):
        for repo in self.state["repos"].values():
            if repo.get("token"):
                message = message.replace(repo["token"], "[REDACTED]")
        message = re.sub(r"(?i)(authorization|password|token)[:=]\S+", r"\1=[REDACTED]", message)
        return message[:4000]

    def event(self, code, level="info", **context):
        entry = {
            "id": uuid.uuid4().hex,
            "time": time.time(),
            "level": level,
            "code": code,
            "message": event_text(code),
            "context": {k: self.redact(str(v)) for k, v in context.items()},
        }
        self.state["events"] = ([entry] + self.state["events"])[:500]
        self.save()
        self.logger.log(
            getattr(logging, level.upper(), logging.INFO), json.dumps(entry, ensure_ascii=False)
        )
        for path in self.data.glob("manager.log*"):
            path.chmod(0o600)

    def snapshot(self):
        return json.loads(self._public)

    def key_create(self, name):
        if not name.strip() or len(name) > 80 or any(ord(c) < 32 for c in name):
            raise Problem("Escribe un nombre de clave de hasta 80 caracteres.")
        key_id = uuid.uuid4().hex
        path = self.data / "keys" / key_id
        run(
            ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "ha-private-git", "-f", str(path)]
        )
        path.chmod(0o600)
        public = path.with_suffix(".pub").read_text().strip()
        self.state["keys"][key_id] = {"id": key_id, "name": name, "public": public}
        self.event("key_created", key_id=key_id)
        return self.state["keys"][key_id]

    def key_delete(self, key_id):
        identifier(key_id)
        if key_id not in self.state["keys"]:
            raise Problem("Clave no encontrada.")
        if any(r.get("key_id") == key_id for r in self.state["repos"].values()):
            raise Problem(
                "La clave está en uso. Cambia la clave de los repositorios antes de eliminarla."
            )
        for path in (self.data / "keys" / key_id, self.data / "keys" / (key_id + ".pub")):
            path.unlink(missing_ok=True)
        del self.state["keys"][key_id]
        self.event("key_deleted", key_id=key_id)

    def scan(self, url):
        scheme, host, port = endpoint(url)
        if scheme != "ssh":
            raise Problem("La verificación de clave de host solo se utiliza con SSH.")
        output = run(["ssh-keyscan", "-T", "8", "-p", str(port), "-t", "ed25519", host], timeout=15)
        lines = [line for line in output.splitlines() if line and not line.startswith("#")]
        if not lines:
            raise Problem("El servidor no devuelve una clave Ed25519.")
        line = lines[0]
        return {"host": host, "port": port, "line": line, "fingerprint": fingerprint(line)}

    def trust(self, url, line, expected):
        scheme, host, port = endpoint(url)
        marker = host if port == 22 else f"[{host}]:{port}"
        if (
            scheme != "ssh"
            or "\n" in line
            or "\r" in line
            or not line.split()
            or line.split()[0] != marker
        ):
            raise Problem("La clave no corresponde al servidor y puerto seleccionados.")
        if fingerprint(line) != expected.strip():
            raise Problem("La huella introducida no coincide con la clave del servidor.")
        self.state["hosts"][f"{host}:{port}"] = {"line": line, "fingerprint": expected.strip()}
        self.event("host_trusted", host=host, port=port)

    def git_env(self, repo):
        scheme, host, port = endpoint(repo["url"])
        env = os.environ.copy()
        # Isolate from global git config, system credential helpers and interactive prompts.
        for key in list(env):
            if key.startswith("GIT_") or key in {"SSH_AUTH_SOCK", "PGM_TOKEN", "PGM_USERNAME"}:
                env.pop(key, None)
        env.pop("SUPERVISOR_TOKEN", None)
        env.update(
            LC_ALL="C",
            HOME=str(self.data / "home"),
            GIT_CONFIG_NOSYSTEM="1",
            GIT_CONFIG_GLOBAL="/dev/null",
            GIT_TERMINAL_PROMPT="0",
            GIT_ASKPASS="/bin/false",
            SSH_ASKPASS="/bin/false",
            GIT_ALLOW_PROTOCOL="ssh:https",
            GIT_LFS_SKIP_SMUDGE="1",
        )
        if scheme == "ssh":
            if not repo.get("key_id") or repo["key_id"] not in self.state["keys"]:
                raise Problem("Selecciona una clave SSH.")
            trusted = self.state["hosts"].get(f"{host}:{port}")
            if not trusted:
                raise Problem("Verifica y guarda primero la identidad del servidor SSH.")
            known = self.data / "known_hosts"
            known.write_text("\n".join(h["line"] for h in self.state["hosts"].values()) + "\n")
            known.chmod(0o600)
            env["GIT_SSH_COMMAND"] = shlex.join(
                [
                    "ssh",
                    "-F",
                    "/dev/null",
                    "-o",
                    "BatchMode=yes",
                    "-o",
                    "StrictHostKeyChecking=yes",
                    "-o",
                    f"UserKnownHostsFile={known}",
                    "-o",
                    "GlobalKnownHostsFile=/dev/null",
                    "-o",
                    "IdentitiesOnly=yes",
                    "-o",
                    "IdentityAgent=none",
                    "-o",
                    "UpdateHostKeys=no",
                    "-o",
                    "ConnectTimeout=15",
                    "-i",
                    str(self.data / "keys" / repo["key_id"]),
                ]
            )
        elif repo.get("token"):
            env.update(
                GIT_ASKPASS=str(self.askpass),
                PGM_USERNAME=repo.get("username") or "git",
                PGM_TOKEN=repo["token"],
            )
        return env

    def repo_add(self, name, url, ref, key_id=None, token=None, username="git"):
        scheme, _, _ = endpoint(url)
        validate_ref(ref)
        if not name.strip() or len(name) > 80 or any(ord(c) < 32 for c in name):
            raise Problem("Escribe un nombre de repositorio de hasta 80 caracteres.")
        repo_id = uuid.uuid4().hex
        repo = {
            "id": repo_id,
            "name": name,
            "url": url,
            "ref": ref,
            "key_id": key_id if scheme == "ssh" else None,
            "token": token if scheme == "https" else None,
            "username": username,
            "commit": None,
            "apps": [],
            "created_at": time.time(),
            "sync_interval": 0,
        }
        self.git_env(repo)  # Validate credentials/trust before recording.
        self.state["repos"][repo_id] = repo
        self.event("repo_added", repo_id=repo_id)
        return repo_id

    def repo(self, repo_id):
        identifier(repo_id)
        if repo_id not in self.state["repos"]:
            raise Problem("Repositorio no encontrado.")
        return self.state["repos"][repo_id]

    def sync(self, repo_id):
        repo = self.repo(repo_id)
        self.event("sync_started", repo_id=repo_id)
        self.progress("fetching")
        env = self.git_env(repo)
        # Fetch into a fresh checkout so failed synchronization cannot damage the last one.
        work = self.data / "repos" / (repo_id + "-pending")
        target = self.data / "repos" / repo_id
        shutil.rmtree(work, ignore_errors=True)
        try:
            run(["git", "init", "--quiet", str(work)], env=env)
            run(["git", "-C", str(work), "config", "core.hooksPath", "/dev/null"], env=env)
            run(["git", "-C", str(work), "remote", "add", "origin", repo["url"]], env=env)
            run(
                [
                    "git",
                    "-C",
                    str(work),
                    "-c",
                    "http.followRedirects=false",
                    "fetch",
                    "--depth",
                    "1",
                    "origin",
                    repo["ref"],
                ],
                env=env,
            )
            run(["git", "-C", str(work), "checkout", "--detach", "--force", "FETCH_HEAD"], env=env)
            commit = run(["git", "-C", str(work), "rev-parse", "HEAD"], env=env)
            apps = self.discover(work)
            catalog = RepositoryDocs(work, repo_id).catalog(apps)
            app_digests = self.app_digests(work, apps)
            previous_apps = {item["slug"]: item for item in repo["apps"]}
            current_apps = {item["slug"]: item for item in apps}
            previous_digests = repo.get("app_digests", {})
            changes = {
                "added": [
                    current_apps[key]["name"] for key in current_apps.keys() - previous_apps.keys()
                ],
                "removed": [
                    previous_apps[key]["name"] for key in previous_apps.keys() - current_apps.keys()
                ],
                "changed": [
                    current_apps[key]["name"]
                    for key in current_apps.keys() & previous_apps.keys()
                    if current_apps[key] != previous_apps[key]
                    or (key in previous_digests and previous_digests[key] != app_digests[key])
                ],
            }
            for names in changes.values():
                names.sort(key=str.casefold)
            self.progress("validating")
            old = self.data / "repos" / (repo_id + "-old")
            shutil.rmtree(old, ignore_errors=True)
            if target.exists():
                target.rename(old)
            try:
                work.rename(target)
            except BaseException:
                if old.exists():
                    old.rename(target)
                raise
            repo.update(
                commit=commit,
                apps=apps,
                catalog=catalog,
                app_digests=app_digests,
                sync_changes=changes,
                synced_at=time.time(),
            )
            self.event("sync_done", repo_id=repo_id, commit=commit)
            shutil.rmtree(old, ignore_errors=True)
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def discover(self, root, *, local=False):
        apps, slugs = [], set()
        for folder, dirs, files in os.walk(root, followlinks=False):
            dirs[:] = sorted(
                d
                for d in dirs
                if not d.startswith(".")
                and d != "rootfs"
                and not (Path(folder) / d).is_symlink()
                and len((Path(folder) / d).relative_to(root).parts) <= 5
            )
            configs = [f for f in ("config.yaml", "config.yml", "config.json") if f in files]
            if not configs:
                continue
            path = Path(folder) / configs[0]
            if path.is_symlink() or path.stat().st_size > 1024 * 1024:
                raise Problem("Configuración enlazada o demasiado grande.")
            try:
                config = yaml.safe_load(path.read_text())
            except (ValueError, yaml.YAMLError, OSError) as exc:
                raise Problem("No se pudo leer la configuración de una aplicación.") from exc
            if not isinstance(config, dict) or not all(
                k in config for k in ("name", "version", "slug", "arch", "description")
            ):
                continue
            if not all(
                isinstance(config[key], str) and config[key].strip()
                for key in ("name", "version", "slug", "description")
            ):
                raise Problem(
                    "Nombre, versión, slug y descripción deben ser textos no vacíos.",
                    "manifest_invalid",
                )
            if config.get("image") is not None and not isinstance(config["image"], str):
                raise Problem("El nombre de imagen no es válido.", "manifest_invalid")
            if config.get("machine") is not None and (
                not isinstance(config["machine"], list)
                or not all(isinstance(item, str) for item in config["machine"])
            ):
                raise Problem("La lista de máquinas no es válida.", "manifest_invalid")
            slug = config["slug"]
            if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{0,79}", slug):
                raise Problem("Slug no válido o reservado para este gestor.")
            if slug in slugs:
                raise Problem("Hay aplicaciones con el mismo slug dentro del repositorio.")
            if (
                not isinstance(config["arch"], list)
                or not config["arch"]
                or not all(
                    isinstance(a, str) and a in {"aarch64", "amd64", "armv7", "armhf", "i386"}
                    for a in config["arch"]
                )
            ):
                raise Problem("La lista de arquitecturas no es válida.")
            slugs.add(slug)
            apps.append(
                {
                    "slug": slug,
                    "name": str(config["name"]),
                    "version": str(config["version"]),
                    "description": str(config["description"]),
                    "arch": config["arch"],
                    "machine": config.get("machine"),
                    "path": str(Path(folder).relative_to(root)),
                    "image": config.get("image"),
                    "ingress": config.get("ingress") is True,
                    "blocked_reason": "manager_self"
                    if slug == "private_git_manager" and not local
                    else None,
                    **RepositoryDocs(root).app_files(str(Path(folder).relative_to(root))),
                }
            )
        return apps

    @staticmethod
    def safe_copy(source, target):
        # Reject all symlinks and special files, even if pointing inside the repository.
        for folder, dirs, files in os.walk(source, followlinks=False):
            dirs[:] = [d for d in dirs if d != ".git"]
            for name in dirs + files:
                path = Path(folder) / name
                mode = path.lstat().st_mode
                if stat.S_ISLNK(mode) or not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
                    raise Problem(
                        "El paquete contiene enlaces simbólicos o archivos especiales; no se copiará."
                    )
        size = sum(
            p.stat().st_size
            for p in source.rglob("*")
            if p.is_file() and ".git" not in p.relative_to(source).parts
        )
        if (
            size > 512 * 1024 * 1024
            or shutil.disk_usage(target.parent).free < size * 2 + 32 * 1024 * 1024
        ):
            raise Problem(
                "El paquete es demasiado grande o no queda suficiente espacio libre.", "disk_space"
            )
        shutil.copytree(source, target, ignore=shutil.ignore_patterns(".git"))

    @staticmethod
    def tree_digest(root):
        digest = hashlib.sha256()
        for path in sorted(root.rglob("*")):
            if ".git" in path.relative_to(root).parts:
                continue
            if path.is_symlink():
                raise Problem("El código contiene enlaces simbólicos.", "manifest_invalid")
            if path.is_file():
                name = str(path.relative_to(root)).encode()
                digest.update(len(name).to_bytes(8, "big"))
                digest.update(name)
                digest.update((path.stat().st_mode & 0o777).to_bytes(4, "big"))
                content = hashlib.sha256()
                with path.open("rb") as stream:
                    while chunk := stream.read(1024 * 1024):
                        content.update(chunk)
                digest.update(content.digest())
        return digest.hexdigest()

    def installed_info(self, slug):
        installed = self.supervisor.call("GET", "/addons").get("addons", [])
        return next((item for item in installed if item["slug"] == "local_" + slug), None)

    def app_digests(self, root, apps):
        result = {}
        for app in apps:
            try:
                result[app["slug"]] = (
                    None
                    if app.get("blocked_reason")
                    else self.tree_digest(Path(root) / app["path"])
                )
            except (Problem, OSError):
                result[app["slug"]] = (
                    None  # Installation still validates unsupported packages explicitly.
                )
        return result

    def read_document(self, repo_id, app_slug=None, kind="readme", path=None):
        repo = self.repo(repo_id)
        if not repo["commit"]:
            raise Problem("Sincroniza primero el repositorio.", "sync_required")
        docs = RepositoryDocs(self.data / "repos" / repo_id, repo_id)
        if path:
            return docs.document(path)
        folder = "."
        if app_slug:
            app = next((a for a in repo["apps"] if a["slug"] == app_slug), None)
            if not app:
                raise Problem("Aplicación no encontrada.", "documentation_missing")
            folder = app["path"]
        files = docs.app_files(folder)
        selected = files["docs_path" if kind == "docs" else "readme_path"]
        return (
            docs.document(selected)
            if selected
            else {"available": False, "path": None, "html": "", "markdown": ""}
        )

    def inspect_deployment(self, repo_id, slug):
        """Describe a local collision without taking ownership or replacing files."""
        repo = self.repo(repo_id)
        app = next((app for app in repo["apps"] if app["slug"] == slug), None)
        if not app or not repo["commit"]:
            raise Problem("Sincroniza el repositorio y selecciona una aplicación detectada.")
        if app.get("blocked_reason"):
            raise Problem(
                "Actualiza este gestor desde Home Assistant; las demás aplicaciones del catálogo sí se pueden gestionar aquí.",
                "manager_self",
            )
        previous = self.state["deployments"].get(slug)
        if previous and previous["repo_id"] != repo_id:
            raise Problem("Otra fuente gestiona una aplicación con este slug.")
        target = self.addons / slug
        if target.is_symlink() or (target.exists() and not target.is_dir()):
            raise Problem(
                "La ruta local no es una carpeta segura y no se puede adoptar.",
                "unsafe_local_folder",
            )
        exists = target.is_dir()
        empty = exists and not any(target.iterdir())
        local_version = None
        local_digest = None
        if exists:
            if not previous and not empty:
                manifests = self.discover(target, local=True)
                if (
                    len(manifests) != 1
                    or manifests[0]["path"] != "."
                    or manifests[0]["slug"] != slug
                ):
                    raise Problem(
                        "La carpeta existente no contiene una aplicación con el mismo identificador. No se sobrescribirá.",
                        "local_manifest_mismatch",
                    )
                local_version = manifests[0]["version"]
            local_digest = self.tree_digest(target)
        installed = self.installed_info(slug)
        docs = RepositoryDocs(self.data / "repos" / repo_id, repo_id)
        names = ("CHANGELOG.md", "CHANGELOG.txt", "CHANGELOG", "CHANGES.md", "changelog.md")
        changelog = docs.find(app["path"], names) or docs.find(".", names)
        notes = ""
        if changelog:
            try:
                notes = docs.text(changelog)[:12000]
            except Problem:
                pass
        return {
            "slug": slug,
            "path": str(target),
            "exists": exists,
            "empty": bool(empty),
            "managed": bool(previous),
            "requires_adoption": bool(exists and not previous and not empty),
            "local_digest": local_digest,
            "local_version": local_version,
            "installed": bool(installed),
            "running": bool(installed and installed.get("state") == "started"),
            "installed_version": installed.get("version") if installed else None,
            "changelog": notes,
            "changelog_path": changelog if notes else None,
            "commit": repo["commit"],
        }

    def deploy(
        self,
        repo_id,
        slug,
        update=False,
        expected_commit=None,
        adopt_existing=False,
        expected_local_digest=None,
        before_update=None,
    ):
        repo = self.repo(repo_id)
        if expected_commit and repo["commit"] != expected_commit:
            raise Problem(
                "El commit ha cambiado desde la confirmación. Revisa los cambios y confirma de nuevo.",
                "commit_changed",
            )
        app = next((a for a in repo["apps"] if a["slug"] == slug), None)
        if not app or not repo["commit"]:
            raise Problem("Sincroniza el repositorio y selecciona una aplicación detectada.")
        if app.get("blocked_reason"):
            raise Problem(
                "Actualiza este gestor desde Home Assistant; las demás aplicaciones del catálogo sí se pueden gestionar aquí.",
                "manager_self",
            )
        if slug in self.state["transactions"]:
            raise Problem(
                "Hay una operación pendiente de recuperar. Revisa la recuperación antes de continuar.",
                "recovery_required",
            )
        local = "local_" + slug
        previous = self.state["deployments"].get(slug)
        target = self.addons / slug
        if previous and previous["repo_id"] != repo_id:
            raise Problem("Otra fuente gestiona una aplicación con este slug.")
        inspection = self.inspect_deployment(repo_id, slug)
        unmanaged_existing = bool(inspection["exists"] and not previous)
        if inspection["requires_adoption"] and not adopt_existing:
            raise Problem("La carpeta local ya existe y no pertenece a este gestor.")
        if adopt_existing and (not unmanaged_existing or not expected_local_digest):
            raise Problem(
                "Revisa la carpeta existente antes de confirmar su adopción.",
                "adoption_confirmation_required",
            )
        if expected_local_digest and inspection["local_digest"] != expected_local_digest:
            raise Problem(
                "La carpeta local ha cambiado desde la revisión. Compruébala y confirma de nuevo.",
                "local_folder_changed",
            )
        if not previous and update:
            raise Problem(
                "Utiliza Actualizar para aplicaciones ya gestionadas; Instalar para nuevas."
            )
        info = self.installed_info(slug)
        if unmanaged_existing or previous:
            update = bool(info)
        if bool(info) != update:
            raise Problem(
                "El estado instalado no coincide. Revisa la aplicación en Home Assistant."
            )
        for candidate in self.discover(self.addons, local=True):
            if candidate["slug"] == slug and candidate["path"] != slug:
                raise Problem("Otra carpeta local ya utiliza este slug.")
        root = self.data / "repos" / repo_id
        self.verify_checkout(repo, root)
        source = (root / app["path"]).resolve()
        if not source.is_relative_to(root.resolve()):
            raise Problem("Ruta de aplicación fuera del repositorio.")
        # Re-read the downloaded manifest immediately before installation.
        fresh = next((a for a in self.discover(root) if a["slug"] == slug), None)
        if len(self.discover(source)) != 1:
            raise Problem(
                "El paquete contiene otras aplicaciones anidadas. Separa sus carpetas antes de instalar.",
                "nested_apps",
            )
        if not app.get("image") and not (source / "Dockerfile").is_file():
            raise Problem(
                "La aplicación necesita un Dockerfile o una imagen precompilada.",
                "missing_dockerfile",
            )
        if fresh != app:
            raise Problem(
                "El manifiesto descargado ha cambiado. Sincroniza de nuevo.", "manifest_changed"
            )
        if before_update:
            if not info:
                raise Problem(
                    "La copia previa requiere una aplicación instalada.", "app_not_installed"
                )
            before_update()
        stage = self.addons / (".pgm-stage-" + uuid.uuid4().hex)
        backup = self.addons / (".pgm-backup-" + uuid.uuid4().hex)
        was_running = bool(info and info.get("state") == "started")
        record = {
            "repo_id": repo_id,
            "slug": slug,
            "commit": repo["commit"],
            "version": app["version"],
            "ingress": app.get("ingress", False),
            "status": "pending",
            "time": time.time(),
            "previous_commit": previous.get("commit") if previous else None,
        }
        journal = {
            "stage": stage.name,
            "backup": backup.name,
            "previous": previous,
            "record": record,
            "was_running": was_running,
            "phase": "prepared",
            "unmanaged_existing": unmanaged_existing,
            "original_digest": inspection["local_digest"] if unmanaged_existing else None,
        }
        moved = False
        committed = False
        self.event("deploy_started", repo_id=repo_id, slug=slug, commit=repo["commit"])
        try:
            self.progress("staging")
            self.safe_copy(source, stage)
            record["source_digest"] = self.tree_digest(stage)
            if unmanaged_existing and (
                not target.is_dir()
                or target.is_symlink()
                or self.tree_digest(target) != inspection["local_digest"]
            ):
                raise Problem(
                    "La carpeta local ha cambiado desde la revisión. Compruébala y confirma de nuevo.",
                    "local_folder_changed",
                )
            identical_adoption = (
                unmanaged_existing
                and bool(info)
                and str(info.get("version")) == app["version"]
                and inspection["local_digest"] == record["source_digest"]
            )
            self.state["transactions"][slug] = journal
            self.state["deployments"][slug] = record
            self.save()  # Durable before the first destructive operation.
            if was_running and not identical_adoption:
                self.progress("stopping")
                self.supervisor.call("POST", f"/addons/{local}/stop")
            journal["phase"] = "swapping"
            self.save()
            if target.exists():
                target.rename(backup)
            stage.rename(target)
            moved = True
            journal["phase"] = "supervisor"
            self.save()
            self.progress("reloading")
            self.supervisor.call("POST", "/store/reload")
            self.progress("installing" if not update else "rebuilding")
            if identical_adoption:
                pass  # Register identical, already-installed source without rebuilding it.
            elif not update:
                self.supervisor.call("POST", f"/store/addons/{local}/install")
            elif app.get("image") or (
                info.get("version") is not None and str(info["version"]) != app["version"]
            ):
                self.supervisor.call("POST", f"/store/addons/{local}/update")
            else:
                self.supervisor.call("POST", f"/addons/{local}/rebuild")
            # The operation must be visible as installed, not merely return HTTP 200.
            verified = self.installed_info(slug)
            if not verified or str(verified.get("version")) != app["version"]:
                raise SupervisorUncertain(
                    "Supervisor no confirma la versión instalada. Revisa la recuperación.",
                    "supervisor_uncertain",
                )
            self.progress("restoring_state")
            # Rebuild may start a previously stopped app: preserve its original state.
            if was_running and verified.get("state") != "started":
                self.supervisor.call("POST", f"/addons/{local}/start")
            elif not was_running and verified.get("state") == "started":
                self.supervisor.call("POST", f"/addons/{local}/stop")
            record["status"] = "installed"
            record["history"] = (
                [{"commit": repo["commit"], "version": app["version"], "time": time.time()}]
                + (previous or {}).get("history", [])
            )[:20]
            self.state["transactions"].pop(slug, None)
            self.save()
            committed = True
            if unmanaged_existing:
                self.event("local_adopted", slug=slug, path=str(target))
            self.event("deploy_done", slug=slug, commit=repo["commit"])
        except SupervisorUncertain:
            # A disconnected request may still be building. Preserve both source trees.
            record["status"] = "uncertain"
            self.event("deploy_failed", "error", slug=slug, recovery="required")
            raise
        except Exception:
            if committed:
                raise
            if moved:
                shutil.rmtree(target)
            if backup.exists():
                backup.rename(target)
            if slug in self.state["transactions"]:
                failed = dict(previous or record, status="error", attempted_commit=repo["commit"])
                if not previous:
                    failed["commit"] = None
                self.state["deployments"][slug] = failed
                journal["phase"] = "restored"
                # Source is restored; runtime may still need a rebuild/start.
                self.save()
                self.event("deploy_failed", "error", slug=slug, recovery="source_restored")
            raise
        finally:
            if slug not in self.state["transactions"]:
                shutil.rmtree(stage, ignore_errors=True)
                shutil.rmtree(backup, ignore_errors=True)

    def recover(self, slug, accept_current=False, retry_uninstall=False):
        """Explicit recovery after reviewing Supervisor; never guess after a disconnect."""
        if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{0,79}", slug):
            raise Problem("Identificador no válido.")
        removal = self.state["transactions"].get(slug)
        if removal and removal.get("kind") == "remove":
            return self.finish_removal(slug, retry_uninstall)
        if removal and removal.get("kind") == "uninstall":
            return self.finish_uninstall(slug, retry_uninstall)
        transaction = self.state["transactions"].get(slug)
        if not transaction:
            raise Problem("No hay una recuperación pendiente para esta aplicación.")
        self.installed_info(slug)  # Require a reachable Supervisor.
        record = transaction["record"]
        target = self.addons / slug
        backup = self.addons / transaction["backup"]
        stage = self.addons / transaction["stage"]
        if accept_current:
            info = self.installed_info(slug)
            if (
                not target.exists()
                or not info
                or str(info.get("version")) != record["version"]
                or record.get("source_digest") != self.tree_digest(target)
            ):
                raise Problem(
                    "La versión instalada no coincide con la operación pendiente.",
                    "version_mismatch",
                )
            record["status"] = "installed"
            self.state["deployments"][slug] = record
        else:
            if backup.exists():
                if target.exists():
                    shutil.rmtree(target)
                backup.rename(target)
            elif transaction.get("unmanaged_existing"):
                if (
                    not target.is_dir()
                    or target.is_symlink()
                    or self.tree_digest(target) != transaction["original_digest"]
                ):
                    raise Problem(
                        "No se ha podido verificar la carpeta local anterior. Conserva los archivos y revisa la recuperación.",
                        "backup_missing",
                    )
            elif not transaction["previous"] and transaction["phase"] not in {
                "prepared",
                "restored",
            }:
                # A first install may still exist in Supervisor. Keep its source for repair.
                if self.installed_info(slug):
                    raise Problem(
                        "La aplicación llegó a instalarse. Acepta la versión actual o desinstálala desde Home Assistant.",
                        "app_still_installed",
                    )
                shutil.rmtree(target, ignore_errors=True)
            if (
                transaction.get("unmanaged_existing")
                and self.tree_digest(target) != transaction["original_digest"]
            ):
                raise Problem(
                    "No se ha podido verificar la carpeta local anterior. Conserva los archivos y revisa la recuperación.",
                    "backup_missing",
                )
            if transaction["previous"]:
                previous = transaction["previous"]
                expected = previous.get("source_digest")
                if not target.exists() or (expected and self.tree_digest(target) != expected):
                    raise Problem(
                        "No se ha podido verificar la copia de código anterior. Conserva los archivos y revisa la recuperación manual.",
                        "backup_missing",
                    )
                if not expected and transaction["phase"] not in {"prepared", "restored"}:
                    raise Problem(
                        "No se ha podido verificar la copia de código anterior. Conserva los archivos y revisa la recuperación manual.",
                        "backup_missing",
                    )
                self.state["deployments"][slug] = dict(previous, status="error")
            else:
                self.state["deployments"].pop(slug, None)
        self.supervisor.call("POST", "/store/reload")
        self.state["transactions"].pop(slug)
        self.save()
        shutil.rmtree(stage, ignore_errors=True)
        shutil.rmtree(backup, ignore_errors=True)
        self.event("recovered", slug=slug, accepted=accept_current)

    def runtime(self, slug, action):
        if slug not in self.state["deployments"]:
            raise Problem("Esta aplicación no está gestionada aquí.")
        if action not in {"start", "stop", "restart"}:
            raise Problem("Acción no permitida.")
        if slug in self.state["transactions"]:
            raise Problem("Revisa primero la recuperación pendiente.", "recovery_required")
        self.supervisor.call("POST", f"/addons/local_{slug}/{action}")
        self.event("runtime_action", slug=slug, action=action)

    def release(self, slug):
        if slug not in self.state["deployments"] or slug in self.state["transactions"]:
            raise Problem(
                "No se puede desvincular esta aplicación; revisa si tiene una recuperación pendiente."
            )
        if self.installed_info(slug):
            raise Problem(
                "Desinstala primero la aplicación desde el gestor.", "app_still_installed"
            )
        # Keep source deliberately: removing a repository must never delete local app data.
        self.state["deployments"].pop(slug)
        self.event("released", slug=slug)

    def inspect_removal(self, repo_id, slug, allow_installed=False):
        repo = self.repo(repo_id)
        previous = self.state["deployments"].get(slug)
        if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{0,79}", slug) or slug == "private_git_manager":
            raise Problem("No se puede borrar esta aplicación.", "removal_forbidden")
        if previous and previous["repo_id"] != repo_id:
            raise Problem("Otra fuente gestiona una aplicación con este slug.")
        if not previous and not any(a["slug"] == slug for a in repo["apps"]):
            raise Problem("Aplicación no encontrada.", "app_missing")
        if slug in self.state["transactions"]:
            raise Problem("Revisa primero la recuperación pendiente.", "recovery_required")
        target = self.addons / slug
        if target.is_symlink() or (target.exists() and not target.is_dir()):
            raise Problem("La ruta local no es segura.", "unsafe_local_folder")
        if target.exists() and any(target.iterdir()):
            apps = self.discover(target, local=True)
            if len(apps) != 1 or apps[0]["path"] != "." or apps[0]["slug"] != slug:
                raise Problem(
                    "La carpeta local pertenece a otra aplicación.", "local_manifest_mismatch"
                )
        installed = self.installed_info(slug)
        if installed and not previous and (not target.exists() or not any(target.iterdir())):
            raise Problem(
                "No se puede verificar la carpeta de esta aplicación.", "removal_forbidden"
            )
        if installed:
            for candidate in self.discover(self.addons, local=True):
                if candidate["slug"] == slug and candidate["path"] != slug:
                    raise Problem("Otra carpeta local ya utiliza este slug.")
        if installed and not allow_installed:
            raise Problem(
                "Desinstala primero la aplicación desde el gestor.", "app_still_installed"
            )
        return {
            "path": str(target),
            "exists": target.exists(),
            "installed": bool(installed),
            "installed_version": installed.get("version") if installed else None,
            "local_digest": self.tree_digest(target) if target.exists() else None,
        }

    def remove_app(
        self,
        repo_id,
        slug,
        expected_local_digest=None,
        hide=True,
        uninstall=False,
        remove_config=False,
    ):
        if remove_config and not uninstall:
            raise Problem("Autoriza primero la desinstalación.", "uninstall_consent")
        inspection = self.inspect_removal(repo_id, slug, allow_installed=uninstall)
        if inspection["local_digest"] != expected_local_digest:
            raise Problem("La carpeta local ha cambiado desde la revisión.", "local_folder_changed")
        # Persist intent before renaming. Recovery removes only this generated staging folder.
        self.state["transactions"][slug] = {
            "kind": "remove",
            "repo_id": repo_id,
            "slug": slug,
            "stage": ".pgm-remove-" + uuid.uuid4().hex,
            "digest": expected_local_digest,
            "hide": hide,
            "uninstall": uninstall,
            "remove_config": remove_config,
            "phase": "prepared",
        }
        self.state["deployments"].setdefault(
            slug,
            {
                "repo_id": repo_id,
                "slug": slug,
                "status": "removing",
                "version": "",
            },
        )
        self.save()
        self.finish_removal(slug)

    def finish_removal(self, slug, retry_uninstall=False):
        transaction = self.state["transactions"][slug]
        stage_name = transaction.get("stage", "")
        if transaction.get("kind") != "remove" or not re.fullmatch(
            r"\.pgm-remove-[a-f0-9]{32}", stage_name
        ):
            raise Problem("No se puede verificar la eliminación pendiente.", "removal_forbidden")
        target, stage = self.addons / slug, self.addons / stage_name
        if stage.is_symlink() or target.is_symlink():
            raise Problem("La ruta local no es segura.", "unsafe_local_folder")
        if transaction["phase"] == "prepared":
            # Recheck reviewed source before uninstalling; a stale confirmation cannot erase data.
            if target.exists() and self.tree_digest(target) != transaction["digest"]:
                raise Problem(
                    "La carpeta local ha cambiado desde la revisión.", "local_folder_changed"
                )
            if not stage.exists():
                self.perform_uninstall(slug, transaction, retry_uninstall)
            if target.exists():
                if stage.exists() or self.tree_digest(target) != transaction["digest"]:
                    raise Problem(
                        "La carpeta local ha cambiado desde la revisión.", "local_folder_changed"
                    )
                target.rename(stage)
            elif not stage.exists() and transaction["digest"] is not None:
                raise Problem("No se encuentra la carpeta revisada.", "local_folder_changed")
            transaction["phase"] = "staged"
            self.save()
        if self.installed_info(slug):
            raise Problem("La aplicación sigue instalada.", "app_still_installed")
        # A new folder at the original location is never part of this deletion.
        self.supervisor.call("POST", "/store/reload")
        if stage.exists() and transaction["phase"] != "purging":
            if self.tree_digest(stage) != transaction["digest"]:
                raise Problem(
                    "La carpeta local ha cambiado desde la revisión.", "local_folder_changed"
                )
        transaction["phase"] = "purging"
        self.save()
        if stage.exists():
            shutil.rmtree(stage)
        repo = self.repo(transaction["repo_id"])
        if transaction["hide"]:
            repo["hidden_apps"] = sorted(set(repo.get("hidden_apps", [])) | {slug})
        self.state["deployments"].pop(slug, None)
        self.state["transactions"].pop(slug)
        self.event("app_removed", repo_id=repo["id"], slug=slug, hidden=transaction["hide"])

    def perform_uninstall(self, slug, transaction, retry=False):
        if not self.installed_info(slug):
            return
        if not transaction.get("uninstall"):
            raise Problem("Autoriza primero la desinstalación.", "uninstall_consent")
        if transaction.get("uninstall_requested") and not retry:
            raise SupervisorUncertain(
                "Comprueba el Supervisor antes de reintentar la desinstalación.",
                "uninstall_uncertain",
            )
        transaction["uninstall_requested"] = True
        self.save()  # Durable before the Supervisor can remove any app data.
        self.progress("uninstalling")
        self.supervisor.call(
            "POST",
            f"/addons/local_{slug}/uninstall",
            {
                "remove_config": bool(transaction.get("remove_config", False)),
            },
        )
        if self.installed_info(slug):
            raise SupervisorUncertain(
                "El Supervisor aún muestra la aplicación instalada.", "uninstall_uncertain"
            )

    def uninstall_app(self, repo_id, slug, expected_local_digest=None, remove_config=False):
        inspection = self.inspect_removal(repo_id, slug, allow_installed=True)
        if inspection["local_digest"] != expected_local_digest:
            raise Problem("La carpeta local ha cambiado desde la revisión.", "local_folder_changed")
        repo = self.repo(repo_id)
        self.state["transactions"][slug] = {
            "kind": "uninstall",
            "repo_id": repo_id,
            "slug": slug,
            "uninstall": True,
            "remove_config": remove_config,
        }
        self.state["deployments"].setdefault(
            slug,
            {
                "repo_id": repo_id,
                "slug": slug,
                "status": "uninstalling",
                "version": inspection["installed_version"] or "",
                "commit": repo.get("commit"),
                "source_digest": inspection["local_digest"],
            },
        )
        self.save()
        self.finish_uninstall(slug)

    def finish_uninstall(self, slug, retry=False):
        transaction = self.state["transactions"][slug]
        self.perform_uninstall(slug, transaction, retry)
        self.state["deployments"][slug]["status"] = "uninstalled"
        self.state["transactions"].pop(slug)
        self.event(
            "app_uninstalled",
            repo_id=transaction["repo_id"],
            slug=slug,
            remove_config=transaction.get("remove_config", False),
        )

    def restore_app(self, repo_id, slug):
        repo = self.repo(repo_id)
        repo["hidden_apps"] = [s for s in repo.get("hidden_apps", []) if s != slug]
        self.event("app_restored", repo_id=repo_id, slug=slug)

    def repo_edit(self, repo_id, name, ref, sync_interval=0):
        repo = self.repo(repo_id)
        validate_ref(ref)
        if not name.strip() or len(name) > 80 or any(ord(c) < 32 for c in name):
            raise Problem("Escribe un nombre válido de hasta 80 caracteres.")
        if sync_interval != 0 and not 300 <= sync_interval <= 604800:
            raise Problem("El intervalo debe ser 0 o estar entre 300 y 604800 segundos.")
        if repo["ref"] != ref:
            # Never install the old checkout while showing a newly selected branch.
            repo.update(commit=None, apps=[], catalog=None, app_digests={}, sync_changes={})
        repo.setdefault("created_at", time.time())
        repo.update(name=name.strip(), ref=ref, sync_interval=sync_interval)
        self.event("repo_edited", repo_id=repo_id)

    def host_delete(self, host_id):
        if host_id not in self.state["hosts"]:
            raise Problem("Servidor no encontrado.")
        for repo in self.state["repos"].values():
            scheme, host, port = endpoint(repo["url"])
            if scheme == "ssh" and f"{host}:{port}" == host_id:
                raise Problem("Este servidor está en uso por un repositorio.")
        self.state["hosts"].pop(host_id)
        self.event("host_deleted", host=host_id)

    def repo_delete(self, repo_id):
        self.repo(repo_id)
        if any(d["repo_id"] == repo_id for d in self.state["deployments"].values()):
            raise Problem("El repositorio tiene aplicaciones gestionadas y no se puede eliminar.")
        shutil.rmtree(self.data / "repos" / repo_id, ignore_errors=True)
        del self.state["repos"][repo_id]
        self.event("repo_deleted", repo_id=repo_id)
