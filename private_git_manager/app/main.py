import json
import os
import shutil
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .application import Applications
from .core import VERSION, Manager, Problem, endpoint
from .documentation import RepositoryDocs
from .jobs import Jobs, Scheduler
from .messages import event_text

manager = Manager(
    os.environ.get("PGM_DATA", ".dev-data"), os.environ.get("PGM_ADDONS", ".dev-addons")
)
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


def response_error(message, code, status=400):
    return JSONResponse({"detail": message, "code": code}, status_code=status)


@app.middleware("http")
async def access_control(request: Request, call_next):
    peer = request.client.host if request.client else ""
    dev = os.environ.get("PGM_DEV") == "1" and not os.environ.get("SUPERVISOR_TOKEN")
    allowed = {"127.0.0.1", "::1", "testclient"} if dev else {"172.30.32.2"}
    # Health check from inside the container exposes only a boolean, no state.
    if request.url.path == "/health" and request.method == "GET" and peer in {"127.0.0.1", "::1"}:
        return JSONResponse({"ok": True})
    if peer not in allowed:
        return response_error(
            "Accede a través de Ingress de Home Assistant.", "ingress_required", 403
        )
    if request.method not in {"GET", "HEAD"} and request.headers.get("X-PGM-Request") != "1":
        return response_error("Petición sin protección CSRF.", "csrf", 403)
    if request.headers.get("sec-fetch-site") == "cross-site":
        return response_error("Origen no autorizado.", "origin", 403)
    length = request.headers.get("content-length")
    if length and (not length.isdigit() or int(length) > 32 * 1024):
        return response_error("La petición es demasiado grande.", "body_limit", 413)
    # Enforce the actual byte count too, including chunked transfer encoding.
    if request.method not in {"GET", "HEAD"}:
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
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.exception_handler(Problem)
async def problem_handler(request, exc):
    return response_error(manager.redact(str(exc)), exc.code, 409 if exc.code == "busy" else 400)


@app.exception_handler(RequestValidationError)
async def validation_handler(request, exc):
    # FastAPI's default response may echo a submitted secret in its input field.
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


class PreflightInput(Input):
    slug: str = Field(min_length=1, max_length=80)


class DeployInput(ConfirmInput):
    slug: str = Field(max_length=80)
    update: bool = False
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


@app.get("/api/state")
def state():
    result = manager.snapshot()
    result["jobs"] = jobs.snapshot()
    result["disk"] = {
        "data_free": shutil.disk_usage(manager.data).free,
        "addons_free": shutil.disk_usage(manager.addons).free,
    }
    return result


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
        return {"connected": False, "addons": [], "reason": "development"}
    # Independent read; must not wait for the job's mutation lock.
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
    # keyscan has no side effects and can run while a job is active.
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
