import json
import os
import re
import shutil
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from tempfile import TemporaryFile
from threading import Lock

from anyio import CancelScope
from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import (
    FileResponse,
    JSONResponse,
    PlainTextResponse,
    Response,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from . import integrations, yunohost
from .application import Applications
from .backups import Backups
from .core import VERSION, Manager, Problem, endpoint
from .documentation import RepositoryDocs
from .jobs import Jobs, Scheduler
from .messages import event_text
from .migration import Migration
from .storage import migrate_app_data

YUNOHOST = os.environ.get("PGM_PLATFORM") == "yunohost"
if YUNOHOST and os.environ.get("SUPERVISOR_TOKEN"):
    raise RuntimeError("El modo YunoHost requiere un entorno independiente del Supervisor.")

data_path = Path(os.environ.get("PGM_DATA", ".dev-data"))
legacy_path = os.environ.get("PGM_LEGACY_DATA")
if legacy_path:
    migrate_app_data(Path(legacy_path), data_path)
manager = Manager(data_path, os.environ.get("PGM_ADDONS", ".dev-addons"))
jobs = Jobs(manager)
scheduler = Scheduler(manager, jobs)


@asynccontextmanager
async def lifespan(app):
    scheduler.start()
    with manager.lock:
        manager.event("startup", version=VERSION)
    yield
    scheduler.close()
    jobs.close()


app = FastAPI(
    title="HA Private Git Manager",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
static = Path(__file__).parent / "static"
UPLOAD_LIMIT = 512 * 1024**2
upload_lock = Lock()
UPLOAD_PATH = re.compile(r"/api/repos/[^/]+/apps/[^/]+/backups/import$")


def response_error(message, code, status=400):
    return JSONResponse({"detail": message, "code": code}, status_code=status)


@app.middleware("http")
async def access_control(request: Request, call_next):
    peer = request.client.host if request.client else ""
    dev = os.environ.get("PGM_DEV") == "1" and not os.environ.get("SUPERVISOR_TOKEN")
    allowed = {"127.0.0.1", "::1", "testclient"} if dev else {"172.30.32.2"}
    # La comprobación interna del contenedor devuelve únicamente un booleano.
    if request.url.path == "/health" and request.method == "GET" and peer in {"127.0.0.1", "::1"}:
        return JSONResponse({"ok": True})
    if YUNOHOST:
        # Uvicorn deja client vacío en sockets Unix. Nginx controla el acceso al socket
        # y añade el marcador tras validar el permiso de YunoHost.
        if request.client is not None or request.headers.get("X-PGM-Proxy") != "yunohost":
            return response_error("Accede desde el portal de YunoHost.", "yunohost_required", 403)
    elif peer not in allowed:
        return response_error(
            "Accede a través de Ingress de Home Assistant.", "ingress_required", 403
        )
    if request.method not in {"GET", "HEAD"} and request.headers.get("X-PGM-Request") != "1":
        return response_error("Petición sin protección CSRF.", "csrf", 403)
    if request.headers.get("sec-fetch-site") == "cross-site":
        return response_error("Origen no autorizado.", "origin", 403)
    upload = request.method == "POST" and UPLOAD_PATH.search(request.url.path)
    limit = UPLOAD_LIMIT if upload else 32 * 1024
    length = request.headers.get("content-length")
    if length and (not length.isdigit() or int(length) > limit):
        return response_error("La petición es demasiado grande.", "body_limit", 413)
    # Limita también el tamaño real del cuerpo cuando llega por fragmentos.
    if request.method not in {"GET", "HEAD"} and not upload:
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 32 * 1024:
                return response_error("La petición es demasiado grande.", "body_limit", 413)
        request._body = bytes(body)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; form-action 'self'; object-src 'none'"
    )
    if YUNOHOST:
        response.headers["Content-Security-Policy"] += "; frame-ancestors 'self'"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.exception_handler(Problem)
async def problem_handler(request, exc):
    return response_error(manager.redact(str(exc)), exc.code, 409 if exc.code == "busy" else 400)


@app.exception_handler(RequestValidationError)
async def validation_handler(request, exc):
    # La respuesta de validación de FastAPI puede devolver un secreto en el campo input.
    return response_error("Revisa los campos introducidos.", "validation", 422)


@app.exception_handler(Exception)
async def internal_handler(request, exc):
    return response_error(
        "Error interno. Consulta los registros de la aplicación.", "internal_error", 500
    )


@contextmanager
def mutation():
    if not manager.lock.acquire(blocking=False):
        raise Problem("Hay una operación en curso. Espera a que termine.", "busy")
    try:
        yield
    finally:
        manager.lock.release()


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class KeyInput(Input):
    name: str = Field(min_length=1, max_length=80)


class HostInput(Input):
    url: str = Field(min_length=1, max_length=2048)


class TrustInput(HostInput):
    line: str = Field(min_length=1, max_length=2048)
    fingerprint: str = Field(max_length=128)


class RepoInput(KeyInput):
    url: str = Field(min_length=1, max_length=2048)
    ref: str = Field(default="main", max_length=200)
    key_id: str | None = Field(default=None, max_length=64)
    token: str | None = Field(default=None, max_length=4096)
    username: str = Field(default="git", max_length=128)


class RepoEdit(KeyInput):
    ref: str = Field(min_length=1, max_length=200)
    sync_interval: int = Field(default=0, ge=0, le=604800)


class CredentialInput(Input):
    key_id: str | None = Field(default=None, max_length=64)
    token: str | None = Field(default=None, max_length=4096)
    username: str = Field(default="git", max_length=128)


class ConfirmInput(Input):
    confirmed: bool = False


class IntegrationInput(Input):
    domain: str = Field(pattern=r"^[a-z][a-z0-9_]{0,79}$")


class IntegrationDeploy(IntegrationInput, ConfirmInput):
    expected_commit: str = Field(pattern=r"^(?:[a-f0-9]{40}|[a-f0-9]{64})$")
    expected_local_digest: str | None = Field(pattern=r"^[a-f0-9]{64}$")
    adopt_existing: bool = False


class MigrationExport(Input):
    recipient: str = Field(min_length=1, max_length=128)


class MigrationRead(Input):
    copy_id: str = Field(min_length=1, max_length=64)
    commit: str = Field(min_length=40, max_length=64)
    identity: str = Field(min_length=1, max_length=128)


class MigrationImport(MigrationRead, ConfirmInput):
    pass


class YunoHostStageInput(Input):
    expected_commit: str = Field(pattern=r"^(?:[a-f0-9]{40}|[a-f0-9]{64})$")


class PreflightInput(Input):
    slug: str = Field(min_length=1, max_length=80)


class DeployInput(ConfirmInput):
    slug: str = Field(max_length=80)
    update: bool = False
    backup_first: bool = False
    expected_commit: str = Field(min_length=40, max_length=64)
    adopt_existing: bool = False
    expected_local_digest: str | None = Field(default=None, min_length=64, max_length=64)


class UninstallInput(ConfirmInput):
    slug: str = Field(min_length=1, max_length=80)
    expected_local_digest: str | None = Field(default=None, min_length=64, max_length=64)
    remove_config: bool = False


class RemoveInput(UninstallInput):
    hide: bool = True
    uninstall: bool = False


class RecoveryInput(ConfirmInput):
    accept_current: bool = False
    retry_uninstall: bool = False


class ConfigurationInput(Input):
    yaml: str = Field(min_length=1, max_length=24000)


class ConfigurationSave(ConfigurationInput):
    expected_revision: str = Field(min_length=64, max_length=64)
    restart: bool = False
    confirmed: bool = False


class BackupCreate(ConfirmInput):
    name: str = Field(default="", max_length=120, pattern=r"^[^\x00-\x1f\x7f]*$")
    password: str | None = Field(default=None, max_length=1024)


class BackupRestore(ConfirmInput):
    password: str | None = Field(default=None, max_length=1024)


class BackupSchedule(Input):
    hours: int = Field(ge=0, le=720)
    keep: int = Field(ge=1, le=30)
    destination: str | None = Field(default=None, max_length=64)
    password: str | None = Field(default=None, max_length=1024)


class BackupGitTarget(ConfirmInput):
    destination: str = Field(min_length=1, max_length=64)


class BackupGitExport(BackupGitTarget):
    expected_revision: str = Field(min_length=64, max_length=64)


class BackupGitImport(BackupGitTarget):
    copy_id: str = Field(min_length=1, max_length=81)
    commit: str = Field(min_length=40, max_length=64)


class BackupDelete(ConfirmInput):
    expected_revision: str = Field(min_length=64, max_length=64)


def confirmed(body):
    if not body.confirmed:
        raise Problem(
            "Confirma la operación solicitada sobre esta aplicación o repositorio.",
            "confirmation_required",
        )


def queued(request, kind, resource, callback):
    key = request.headers.get("Idempotency-Key", "")
    if len(key) > 128:
        raise Problem("Identificador de petición no válido.", "validation")
    job = jobs.submit(kind, resource, callback, key or None)
    return JSONResponse(job, status_code=202)


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/")
def index():
    return FileResponse(static / "index.html")


def core_integrations():
    config = os.environ.get("PGM_CORE_CONFIG")
    if not config or YUNOHOST or not manager.supervisor.token:
        raise Problem(
            "La gestión de integraciones requiere Home Assistant OS.", "integration_unavailable"
        )
    return integrations.Integrations(manager, config)


@app.post("/api/repos/{repo_id}/integrations/preflight")
def integration_preflight(repo_id: str, body: IntegrationInput):
    with mutation():
        return core_integrations().inspect(repo_id, body.domain)


@app.post("/api/repos/{repo_id}/integrations/deploy")
def integration_deploy(repo_id: str, body: IntegrationDeploy, request: Request):
    confirmed(body)
    installer = core_integrations()
    return queued(
        request,
        "integration_deploy",
        "repo:" + repo_id,
        lambda: installer.deploy(
            repo_id,
            body.domain,
            body.expected_commit,
            body.expected_local_digest,
            body.adopt_existing,
        ),
    )


@app.get("/api/state")
def state():
    result = manager.snapshot()
    if YUNOHOST:
        result["platform"] = "yunohost"
        for repo_id, repo in result["repos"].items():
            if repo.get("commit"):
                repo["yunohost_package"] = yunohost.package(manager.data / "repos" / repo_id)
    elif manager.supervisor.token and os.environ.get("PGM_CORE_CONFIG"):
        installer = core_integrations()
        result["integrations_available"] = installer.available()
        if result["integrations_available"]:
            for repo_id, repo in result["repos"].items():
                if repo.get("commit"):
                    checkout = manager.data / "repos" / repo_id
                    repo["integrations"] = [
                        {**item, **installer.summary(repo_id, item["domain"])}
                        for item in integrations.catalog(checkout)
                    ]
    result["jobs"] = jobs.snapshot()
    result["disk"] = {
        "data_free": shutil.disk_usage(manager.data).free,
        "addons_free": shutil.disk_usage(manager.addons).free,
    }
    return result


@app.get("/api/migration/{repo_id}/copies")
def migration_copies(repo_id: str):
    with mutation():
        return Migration(manager, repo_id).copies()


@app.post("/api/migration/{repo_id}/export")
def migration_export(repo_id: str, body: MigrationExport):
    with mutation():
        return Migration(manager, repo_id).export(body.recipient.strip())


@app.post("/api/migration/{repo_id}/preview")
def migration_preview(repo_id: str, body: MigrationRead):
    with mutation():
        catalog = Migration(manager, repo_id).read(body.copy_id, body.commit, body.identity.strip())
        return catalog.model_dump()


@app.post("/api/migration/{repo_id}/import")
def migration_import(repo_id: str, body: MigrationImport):
    confirmed(body)
    with mutation():
        migration = Migration(manager, repo_id)
        catalog = migration.read(body.copy_id, body.commit, body.identity.strip())
        return migration.apply(catalog)


@app.post("/api/repos/{repo_id}/yunohost-stage")
def yunohost_stage(repo_id: str, body: YunoHostStageInput):
    if not YUNOHOST:
        return response_error("Solo disponible en YunoHost.", "yunohost_only", 404)
    with mutation():
        return yunohost.stage(manager, repo_id, body.expected_commit)


@app.delete("/api/yunohost-stages/{stage_id}")
def yunohost_discard(stage_id: str):
    if not YUNOHOST:
        return response_error("Solo disponible en YunoHost.", "yunohost_only", 404)
    with mutation():
        yunohost.discard(manager.data, stage_id)
    return {"ok": True}


@app.get("/api/logs")
def logs(language: str = "es", level: str = "", query: str = "", download: bool = False):
    events = manager.snapshot()["events"]
    filtered = [
        dict(e, message=event_text(e.get("code", e["message"]), language))
        for e in events
        if (not level or e.get("level", "info") == level)
    ]
    if query:
        filtered = [
            e for e in filtered if query.lower() in json.dumps(e, ensure_ascii=False).lower()
        ]
    if download:
        return PlainTextResponse(
            "\n".join(json.dumps(e, ensure_ascii=False) for e in filtered),
            headers={"Content-Disposition": 'attachment; filename="private-git-manager.jsonl"'},
        )
    return {"events": filtered}


@app.get("/api/supervisor")
def supervisor_status():
    if not manager.supervisor.token:
        reason = "yunohost" if YUNOHOST else "development"
        return {"connected": False, "addons": [], "reason": reason}
    # La lectura del estado del Supervisor debe responder mientras hay trabajos.
    data = manager.supervisor.call("GET", "/addons")
    return {
        "connected": True,
        "addons": [a for a in data.get("addons", []) if a["slug"].startswith("local_")],
    }


@app.post("/api/keys")
def key_create(body: KeyInput):
    with mutation():
        return manager.key_create(body.name)


@app.delete("/api/keys/{key_id}")
def key_delete(key_id: str):
    with mutation():
        manager.key_delete(key_id)
        return {"ok": True}


@app.post("/api/hosts/scan")
def host_scan(body: HostInput):
    # keyscan consulta la huella sin modificar el estado.
    return manager.scan(body.url)


@app.post("/api/hosts/trust")
def host_trust(body: TrustInput):
    with mutation():
        manager.trust(body.url, body.line, body.fingerprint)
        return {"ok": True}


@app.delete("/api/hosts/{host_id}")
def host_delete(host_id: str):
    with mutation():
        manager.host_delete(host_id)
        return {"ok": True}


@app.post("/api/repos")
def repo_add(body: RepoInput):
    with mutation():
        return {"id": manager.repo_add(**body.model_dump())}


@app.patch("/api/repos/{repo_id}")
def repo_edit(repo_id: str, body: RepoEdit):
    with mutation():
        manager.repo_edit(repo_id, **body.model_dump())
        return {"ok": True}


@app.post("/api/repos/{repo_id}/credentials")
def credentials(repo_id: str, body: CredentialInput):
    with mutation():
        repo = manager.repo(repo_id)
        values = body.model_dump()
        if endpoint(repo["url"])[0] == "ssh":
            values["token"] = None
        else:
            values["key_id"] = None
        candidate = dict(repo, **values)
        manager.git_env(candidate)
        repo.update(values)
        manager.event("credentials_changed", repo_id=repo_id)
        return {"ok": True}


@app.post("/api/repos/{repo_id}/sync")
def sync(repo_id: str, request: Request):
    if repo_id not in manager.snapshot()["repos"]:
        raise Problem("Repositorio no encontrado.")
    return queued(request, "sync", "repo:" + repo_id, lambda: manager.sync(repo_id))


@app.delete("/api/repos/{repo_id}")
def repo_delete(repo_id: str):
    with mutation():
        manager.repo_delete(repo_id)
        return {"ok": True}


@app.get("/api/repos/{repo_id}/document")
def document(
    repo_id: str,
    app_slug: str | None = Query(None, max_length=80),
    kind: str = Query("readme", pattern="^(readme|docs)$"),
    path: str | None = Query(None, max_length=2048),
):
    with mutation():
        return manager.read_document(repo_id, app_slug, kind, path)


@app.get("/api/repos/{repo_id}/asset")
def document_asset(repo_id: str, path: str = Query(min_length=1, max_length=2048)):
    with mutation():
        repo = manager.repo(repo_id)
        if not repo["commit"]:
            raise Problem("Sincroniza primero el repositorio.", "sync_required")
        data, media_type = RepositoryDocs(manager.data / "repos" / repo_id, repo_id).image(path)
        return Response(
            data, media_type=media_type, headers={"Cross-Origin-Resource-Policy": "same-origin"}
        )


@app.post("/api/repos/{repo_id}/preflight")
def preflight(repo_id: str, body: PreflightInput):
    with mutation():
        return manager.inspect_deployment(repo_id, body.slug)


@app.post("/api/repos/{repo_id}/deploy")
def deploy(repo_id: str, body: DeployInput, request: Request):
    confirmed(body)
    return queued(
        request,
        "deploy",
        "repo:" + repo_id,
        lambda: manager.deploy(
            repo_id,
            body.slug,
            body.update,
            body.expected_commit,
            body.adopt_existing,
            body.expected_local_digest,
            before_update=(lambda: Backups(manager).create(repo_id, body.slug))
            if body.backup_first
            else None,
        ),
    )


@app.post("/api/repos/{repo_id}/remove-preflight")
def remove_preflight(repo_id: str, body: PreflightInput):
    with mutation():
        return manager.inspect_removal(repo_id, body.slug, allow_installed=True)


@app.post("/api/repos/{repo_id}/remove-app")
def remove_app(repo_id: str, body: RemoveInput, request: Request):
    confirmed(body)
    return queued(
        request,
        "remove",
        "repo:" + repo_id,
        lambda: manager.remove_app(
            repo_id,
            body.slug,
            body.expected_local_digest,
            body.hide,
            body.uninstall,
            body.remove_config,
        ),
    )


@app.post("/api/repos/{repo_id}/uninstall-app")
def uninstall_app(repo_id: str, body: UninstallInput, request: Request):
    confirmed(body)
    return queued(
        request,
        "uninstall",
        "repo:" + repo_id,
        lambda: manager.uninstall_app(
            repo_id, body.slug, body.expected_local_digest, body.remove_config
        ),
    )


@app.post("/api/repos/{repo_id}/restore-app")
def restore_app(repo_id: str, body: PreflightInput):
    with mutation():
        manager.restore_app(repo_id, body.slug)
        return {"ok": True}


@app.get("/api/repos/{repo_id}/apps/{slug}/backups")
def app_backups(repo_id: str, slug: str):
    return Backups(manager).list(repo_id, slug)


@app.post("/api/repos/{repo_id}/apps/{slug}/backups/schedule")
def set_backup_schedule(repo_id: str, slug: str, body: BackupSchedule):
    with mutation():
        Backups(manager).configure_schedule(
            repo_id, slug, body.hours, body.keep, body.destination, body.password
        )
    return {"ok": True}


@app.get("/api/repos/{repo_id}/apps/{slug}/backups/git")
def list_git_backups(repo_id: str, slug: str, destination: str = Query(max_length=64)):
    with mutation():
        return Backups(manager).git_copies(repo_id, slug, destination)


@app.post("/api/repos/{repo_id}/apps/{slug}/backups/git")
def import_git_backup(repo_id: str, slug: str, body: BackupGitImport, request: Request):
    confirmed(body)
    return queued(
        request,
        "backup_git_import",
        "repo:" + repo_id,
        lambda: Backups(manager).git_import(
            repo_id, slug, body.destination, body.copy_id, body.commit
        ),
    )


@app.post("/api/repos/{repo_id}/apps/{slug}/backups/{selected}/git")
def export_git_backup(
    repo_id: str, slug: str, selected: str, body: BackupGitExport, request: Request
):
    confirmed(body)
    return queued(
        request,
        "backup_git_export",
        "repo:" + repo_id,
        lambda: Backups(manager).git_export(
            repo_id, slug, body.destination, selected, body.expected_revision
        ),
    )


@app.post("/api/repos/{repo_id}/apps/{slug}/backups/import")
async def import_app_backup(repo_id: str, slug: str, request: Request):
    if request.headers.get("content-type") != "application/x-tar":
        raise Problem("Selecciona un archivo .tar de Home Assistant.", "backup_import_invalid")
    if not upload_lock.acquire(blocking=False):
        raise Problem("Ya hay una importación en curso.", "busy")
    try:
        await run_in_threadpool(Applications(manager).target, repo_id, slug, True)
        budget = min(UPLOAD_LIMIT, shutil.disk_usage(manager.data).free - 128 * 1024**2)
        total = 0
        with TemporaryFile(dir=manager.data) as archive:
            async for chunk in request.stream():
                total += len(chunk)
                if total > UPLOAD_LIMIT:
                    return response_error("La copia supera 512 MiB.", "backup_import_size", 413)
                if total > budget:
                    raise Problem(
                        "No hay espacio suficiente para importar la copia.", "backup_import_space"
                    )
                await run_in_threadpool(archive.write, chunk)

            def import_file():
                with mutation():
                    archive.seek(0)
                    return Backups(manager).import_archive(repo_id, slug, archive)

            with CancelScope(shield=True):
                return await run_in_threadpool(import_file)
    except OSError as exc:
        raise Problem("No se pudo escribir la copia temporal.", "backup_import_space") from exc
    finally:
        upload_lock.release()


@app.get("/api/repos/{repo_id}/apps/{slug}/backups/{selected}")
def app_backup_details(repo_id: str, slug: str, selected: str):
    return Backups(manager).details(repo_id, slug, selected)


class BackupStreamingResponse(StreamingResponse):
    def __init__(self, stream, selected):
        self.backup_stream = stream
        super().__init__(
            stream.chunks(),
            media_type="application/x-tar",
            headers={
                **stream.headers,
                "Content-Disposition": f'attachment; filename="ha-backup-{selected}.tar"',
                "Accept-Ranges": "none",
            },
        )

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            # Cierra el archivo incluso si se cancela antes de leer el primer bloque.
            with CancelScope(shield=True):
                await run_in_threadpool(self.backup_stream.close)


@app.get("/api/repos/{repo_id}/apps/{slug}/backups/{selected}/download")
def download_app_backup(
    repo_id: str,
    slug: str,
    selected: str,
    expected_revision: str = Query(min_length=64, max_length=64),
):
    stream = Backups(manager).download(repo_id, slug, selected, expected_revision)
    return BackupStreamingResponse(stream, selected)


@app.post("/api/repos/{repo_id}/apps/{slug}/backups/{selected}/delete")
def delete_app_backup(repo_id: str, slug: str, selected: str, body: BackupDelete, request: Request):
    confirmed(body)
    return queued(
        request,
        "backup_delete",
        "repo:" + repo_id,
        lambda: Backups(manager).delete(repo_id, slug, selected, body.expected_revision),
    )


@app.post("/api/repos/{repo_id}/apps/{slug}/backups")
def create_app_backup(repo_id: str, slug: str, body: BackupCreate, request: Request):
    confirmed(body)
    return queued(
        request,
        "backup_create",
        "repo:" + repo_id,
        lambda: Backups(manager).create(repo_id, slug, body.name, body.password),
    )


@app.post("/api/repos/{repo_id}/apps/{slug}/backups/{selected}/restore")
def restore_app_backup(
    repo_id: str, slug: str, selected: str, body: BackupRestore, request: Request
):
    confirmed(body)
    return queued(
        request,
        "backup_restore",
        "repo:" + repo_id,
        lambda: Backups(manager).restore(repo_id, slug, selected, body.password),
    )


@app.get("/api/repos/{repo_id}/apps/{slug}/web-interface")
def app_web_interface(repo_id: str, slug: str):
    return Applications(manager).web_interface(repo_id, slug)


@app.get("/api/repos/{repo_id}/apps/{slug}/configuration")
def app_configuration(repo_id: str, slug: str):
    return Applications(manager).configuration(repo_id, slug)


@app.post("/api/repos/{repo_id}/apps/{slug}/configuration/convert")
def convert_configuration(repo_id: str, slug: str, body: ConfigurationInput):
    with mutation():
        return Applications(manager).convert(repo_id, slug, body.yaml)


@app.post("/api/repos/{repo_id}/apps/{slug}/configuration/validate")
def validate_configuration(repo_id: str, slug: str, body: ConfigurationInput):
    with mutation():
        Applications(manager).validate(repo_id, slug, body.yaml)
        return {"valid": True}


@app.post("/api/repos/{repo_id}/apps/{slug}/configuration")
def save_configuration(repo_id: str, slug: str, body: ConfigurationSave, request: Request):
    confirmed(body)
    return queued(
        request,
        "configure",
        "repo:" + repo_id,
        lambda: Applications(manager).save(
            repo_id, slug, body.yaml, body.expected_revision, body.restart
        ),
    )


@app.get("/api/repos/{repo_id}/apps/{slug}/logs")
def app_logs(repo_id: str, slug: str, download: bool = False):
    result = Applications(manager).logs(repo_id, slug)
    if download:
        return PlainTextResponse(
            result["text"], headers={"Content-Disposition": f'attachment; filename="{slug}.log"'}
        )
    return result


@app.post("/api/apps/{slug}/recover")
def recover(slug: str, body: RecoveryInput, request: Request):
    confirmed(body)
    return queued(
        request,
        "recover",
        "app:" + slug,
        lambda: manager.recover(slug, body.accept_current, body.retry_uninstall),
    )


@app.post("/api/apps/{slug}/release")
def release(slug: str, body: ConfirmInput):
    confirmed(body)
    with mutation():
        manager.release(slug)
        return {"ok": True}


@app.post("/api/apps/{slug}/{action}")
def runtime(slug: str, action: str, body: ConfirmInput, request: Request):
    confirmed(body)
    return queued(request, action, "app:" + slug, lambda: manager.runtime(slug, action))


app.mount("/static", StaticFiles(directory=static), name="static")
