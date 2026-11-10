"""Panel y API: ciclo de vida único, permisos, traducciones y secretos enmascarados."""
import asyncio
import json
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import Settings, hash_password
from .smtp import start_smtp
from .store import Store
from .worker import Worker
from .telegram import TelegramClient, TelegramError
from .streams import StreamManager
from .diagnostics import TestEmail, analyze_image, send_test_email
from .server import ENV_FIELDS, ServerSettings, deployment
from .auth import AuthPolicy
from . import __version__
from .i18n import (N_, tr, browser_catalogs, current_language, negotiate_language,
                   service_language, set_service_language, translate_saved, use_language)

MASK = "********"


async def read_body(request, limit):
    content_length = request.headers.get("content-length")
    if content_length and (not content_length.isdigit() or int(content_length) > limit):
        raise HTTPException(413, tr("El archivo o la petición supera el tamaño permitido"))
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > limit:
            raise HTTPException(413, tr("El archivo o la petición supera el tamaño permitido"))
    return body


def create_app(store=None, start_services=True, server_settings=None):
    """Construye una instancia; las pruebas pueden omitir SMTP, trabajador y cámaras."""
    store = store or Store()
    set_service_language(store.settings().language)
    running = server_settings or store.server_settings().effective()
    worker = Worker(store)
    models = worker.detector.models
    streams = StreamManager(store, worker.detector)
    test_lock = threading.Lock()
    auth_policy = AuthPolicy()

    @asynccontextmanager
    async def lifespan(app):
        controller = None
        if start_services:
            controller = await asyncio.to_thread(start_smtp, store, running)
            worker.start()
            streams.start()
        try:
            yield
        finally:
            await asyncio.to_thread(models.stop)
            await asyncio.to_thread(streams.stop)
            if controller:
                controller.stop()
            await asyncio.to_thread(worker.stop)

    app = FastAPI(
        title="PiVigia", version=__version__, lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None
    )
    app.state.store = store
    app.state.worker = worker
    app.state.models = models
    app.state.streams = streams
    app.state.auth_policy = auth_policy

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, error):
        return JSONResponse({"detail": tr("Petición no válida. Revisa los parámetros enviados.")}, status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request, error):
        default_messages = {404: ("Not Found", N_("Recurso no encontrado")),
                            405: ("Method Not Allowed", N_("Método no permitido"))}
        original, message = default_messages.get(error.status_code, (None, None))
        detail = tr(message) if original and error.detail == original else error.detail
        return JSONResponse({"detail": detail}, status_code=error.status_code, headers=error.headers)

    def run_test(callback, *args):
        if not test_lock.acquire(blocking=False):
            raise HTTPException(409, tr("Ya hay una prueba en curso. Espera a que termine."))
        try:
            return callback(*args)
        finally:
            test_lock.release()

    @app.middleware("http")
    async def authenticate(request: Request, call_next):
        with use_language(negotiate_language(request.headers.get("accept-language"))):
            response = await authenticated_response(request, call_next)
            response.headers["Content-Language"] = current_language()
            response.headers["Vary"] = "Accept-Language"
            return response

    async def authenticated_response(request: Request, call_next):
        path = request.url.path
        response = None
        public_options = path == "/api/auth/options" and request.method == "GET"
        if path.startswith("/api/") and not public_options:
            identity = auth_policy.identify(request, store.token)
            request.state.identity = identity
            if identity is None:
                response = JSONResponse({"detail": tr("Inicia sesión con un token válido o abre PiVigia desde Home Assistant con un Supervisor que envíe los grupos del usuario.")},
                                        status_code=401)
            elif not auth_policy.permits(identity, request.method, path):
                response = JSONResponse({"detail": tr("Tu acceso es de solo consulta. Esta operación requiere un administrador de PiVigia.")}, status_code=403)
            elif (identity.provider == "homeassistant" and request.method not in {"GET", "HEAD", "OPTIONS"}
                  and request.headers.get("x-pivigia-request") != "1"):
                response = JSONResponse({"detail": tr("Petición de formulario no válida. Usa el panel de PiVigia.")},
                                        status_code=403)
        if response is None:
            response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; connect-src 'self'; base-uri 'self'; form-action 'self'"
        )
        return response

    @app.get("/api/auth/options")
    def auth_options():
        return auth_policy.options()

    @app.get("/api/auth/session")
    def auth_session(request: Request):
        return request.state.identity.public()

    @app.get("/", response_class=HTMLResponse)
    def index():
        data = {"catalogs": browser_catalogs(), "default_language": service_language(),
                "language_locked": bool(os.environ.get("PIVIGIA_LANGUAGE"))}
        # El catálogo es dato, nunca marcado ejecutable; escapar también el cierre </script>.
        payload = json.dumps(data, ensure_ascii=True).replace("<", "\\u003c").replace("&", "\\u0026")
        return ((Path(__file__).parent / "static" / "index.html").read_text()
                .replace("__PIVIGIA_VERSION__", __version__).replace("__PIVIGIA_I18N__", payload))

    @app.get("/healthz")
    def health():
        return {"status": "ok"}

    @app.get("/api/status")
    def status():
        return {
            "name": "PiVigia",
            "version": __version__,
            "language": service_language(),
            "model_ready": worker.detector.ready(),
            "model": models.active,
            "worker_alive": bool(worker.thread and worker.thread.is_alive()),
            "counts": store.stats(),
            "detections": store.detection_status(),
        }

    @app.get("/api/server")
    def server():
        saved = store.server_settings()
        effective = saved.effective()
        return {"deployment": deployment(), "editable": deployment() == "local",
                "running": running.model_dump(), "saved": saved.model_dump(),
                "effective": effective.model_dump(), "restart_required": effective != running,
                "environment_fields": [key for key, variable in ENV_FIELDS.items() if variable in os.environ]}

    @app.put("/api/server")
    async def save_server(request: Request):
        if deployment() != "local":
            raise HTTPException(409, tr("En Home Assistant usa Configuración y Red del complemento; en Docker cambia .env y los puertos de Compose y recrea el contenedor."))
        try:
            proposed = ServerSettings.model_validate_json(await read_body(request, 10_000))
            current = store.server_settings().effective()
            for key, variable in ENV_FIELDS.items():
                if variable in os.environ and getattr(proposed, key) != getattr(current, key):
                    raise HTTPException(409, tr("El ajuste {key} está fijado por {variable}. Cambia esa variable.", key=key, variable=variable))
            proposed.effective()
        except ValueError:
            raise HTTPException(422, tr("Revisa las IP de escucha, los puertos (1024–65535, diferentes), las redes permitidas y las dos rutas absolutas de TLS.")) from None
        await asyncio.to_thread(store.save_server_settings, proposed)
        return {"ok": True, "restart_required": proposed.effective() != running,
                "detail": tr("Guardado. Reinicia PiVigia para aplicar los cambios de servidor.")}

    @app.get("/api/models")
    def model_catalog():
        return models.status()

    @app.post("/api/models/{model}/download", status_code=202)
    def download_model(model: str):
        try:
            return models.start_download(model)
        except ValueError as error:
            raise HTTPException(409, str(error)) from None

    @app.post("/api/models/cancel")
    def cancel_model_download():
        models.cancel.set()
        return {"ok": True}

    @app.post("/api/models/{model}/activate")
    def activate_model(model: str):
        try:
            return models.activate(model)
        except ValueError as error:
            raise HTTPException(409, str(error)) from None
        except Exception:
            raise HTTPException(503, tr("No se pudo cargar el modelo. La selección anterior se conserva.")) from None

    @app.delete("/api/models/{model}")
    def delete_model(model: str):
        try:
            return models.delete(model)
        except ValueError as error:
            raise HTTPException(409, str(error)) from None

    @app.post("/api/tests/email")
    async def test_email(request: Request):
        try:
            test = TestEmail.model_validate_json(await read_body(request, 20_000))
        except ValueError:
            raise HTTPException(422, tr("Indica un destinatario válido, un asunto sin saltos de línea y un texto de hasta 5000 caracteres.")) from None
        settings = await asyncio.to_thread(store.settings)
        if not settings.smtp_host or not settings.smtp_from:
            raise HTTPException(422, tr("Guarda primero el servidor SMTP de salida y el remitente en Configuración."))
        try:
            return await asyncio.to_thread(run_test, send_test_email, settings, test)
        except ValueError as error:
            raise HTTPException(422, str(error)) from None

    @app.post("/api/tests/image")
    async def test_image(request: Request, mailbox: str = "", model: str = ""):
        settings = await asyncio.to_thread(store.settings)
        content = bytes(await read_body(request, settings.max_image_bytes))
        if not content:
            raise HTTPException(422, tr("Selecciona una imagen antes de analizar."))
        if model:
            try:
                if not models.installed(model):
                    raise ValueError(tr("Descarga el modelo antes de probarlo."))
            except ValueError as error:
                raise HTTPException(409, str(error)) from None
        try:
            return await asyncio.to_thread(run_test, analyze_image, settings, worker.detector, content, mailbox, model)
        except ValueError:
            # Mostrar solo este error validado; los errores nativos de imagen pueden incluir entradas.
            if mailbox and not any(b.address == mailbox for b in settings.mailboxes):
                raise HTTPException(422, tr("El buzón seleccionado no existe. Actualiza la página.")) from None
            raise HTTPException(422, tr("No se pudo analizar la imagen. Comprueba que el archivo sea válido.")) from None
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, tr("Detector no disponible. Comprueba el modelo y el registro del servicio.")) from None

    @app.get("/api/events")
    def events():
        result = store.events()
        for item in result:
            item["result"] = json.loads(item["result"])
            item["result"]["skipped"] = [translate_saved(message) for message in item["result"].get("skipped", [])]
            item["error"] = translate_saved(item["error"])
            item["delivered"] = json.loads(item["delivered"])
        return result

    @app.get("/api/cameras")
    def cameras():
        settings = store.settings()
        return {"enabled": settings.rtsp_enabled, "cameras": streams.status(settings),
                "events": store.camera_events(),
                "smtp_busy": bool(store.stats().get("queued") or store.stats().get("processing"))}

    @app.get("/api/cameras/{camera_id}/preview")
    def camera_preview(camera_id: str):
        jpeg = streams.preview(camera_id, store.settings())
        if jpeg is None:
            raise HTTPException(404, tr("Todavía no hay imagen disponible"))
        return Response(jpeg, media_type="image/jpeg")

    @app.get("/api/settings")
    def settings():
        result = store.settings().model_dump()
        result["language"] = service_language(result["language"])
        result["smtp_password"] = MASK if result["smtp_password"] else ""
        result["telegram_bot_token"] = MASK if result["telegram_bot_token"] else ""
        for box in result["mailboxes"]:
            box["password"] = MASK
        for camera in result["cameras"]:
            camera["url"] = MASK
        return result

    @app.put("/api/settings")
    async def save(request: Request, content_length: str | None = Header(default=None)):
        if content_length and (not content_length.isdigit() or int(content_length) > 100_000):
            raise HTTPException(413, tr("Configuración demasiado grande"))
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 100_000:
                raise HTTPException(413, tr("Configuración demasiado grande"))
        try:
            settings = Settings.model_validate_json(body)
            if os.environ.get("PIVIGIA_LANGUAGE"):
                settings.language = service_language()
            old = store.settings()
            existing_cameras = {camera.id: camera for camera in old.cameras}
            for camera in settings.cameras:
                if camera.url == MASK:
                    if camera.id not in existing_cameras:
                        raise ValueError(tr("Indica la URL de la nueva cámara"))
                    camera.url = existing_cameras[camera.id].url
            if settings.smtp_password == MASK:
                settings.smtp_password = old.smtp_password
            if settings.telegram_bot_token == MASK:
                settings.telegram_bot_token = old.telegram_bot_token
            existing = {b.address: b for b in old.mailboxes}
            for box in settings.mailboxes:
                if box.password == MASK:
                    if box.address not in existing:
                        raise ValueError(tr("Indica la contraseña del nuevo buzón"))
                    box.password = existing[box.address].password
                else:
                    box.password = await asyncio.to_thread(hash_password, box.password)
            settings = Settings.model_validate(settings.model_dump())
            await asyncio.to_thread(store.save_settings, settings)
            set_service_language(settings.language)
        except ValueError:
            # Los errores de Pydantic incluyen entradas; no devolver secretos al cliente.
            raise HTTPException(
                422,
                tr("Revisa las direcciones, contraseñas (mínimo 8 caracteres), categorías, límites, cámaras RTSP y ajustes de Telegram (token e IDs de chat)"),
            ) from None
        return {"ok": True}

    @app.post("/api/telegram/chats")
    def telegram_chats():
        try:
            return TelegramClient(store.settings().telegram_bot_token).recent_chats()
        except TelegramError as error:
            raise HTTPException(422, str(error)) from None

    @app.post("/api/events/{job_id}/retry")
    def retry(job_id: int):
        if not store.retry(job_id):
            raise HTTPException(409, tr("Solo se pueden reintentar mensajes fallidos conservados"))
        return {"ok": True}

    return app


def main():
    import uvicorn

    store = Store()
    settings = store.server_settings().effective()
    uvicorn.run(
        create_app(store, server_settings=settings),
        host=settings.web_bind,
        port=settings.web_port,
        proxy_headers=False,
    )


if __name__ == "__main__":
    main()
