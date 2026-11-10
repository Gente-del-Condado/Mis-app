"""Cliente mínimo de Telegram Bot API. Sin dependencias ni servicios intermedios."""


import json
import secrets
import ssl
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener
from .i18n import tr


class TelegramError(RuntimeError):
    def __init__(self, message, retry_after=0):
        super().__init__(message)
        self.retry_after = retry_after


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def multipart(fields, photo):
    boundary = "pivigia-" + secrets.token_hex(16)
    chunks = []
    for key, value in fields.items():
        chunks.extend(
            [
                f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n'.encode(),
                str(value).encode("utf-8"),
                b"\r\n",
            ]
        )
    chunks.extend(
        [
            f'--{boundary}\r\nContent-Disposition: form-data; name="photo"; '
            'filename="pivigia.jpg"\r\nContent-Type: image/jpeg\r\n\r\n'.encode(),
            photo,
            f"\r\n--{boundary}--\r\n".encode(),
        ]
    )
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


class TelegramClient:
    def __init__(self, token, transport=None):
        if not token:
            raise TelegramError(tr("Configura el token del bot de Telegram"))
        self.token = token
        self.transport = (
            transport or build_opener(NoRedirect(), HTTPSHandler(context=ssl.create_default_context())).open
        )

    @staticmethod
    def _failure(payload, status):
        parameters = payload.get("parameters")
        retry_after = parameters.get("retry_after", 0) if isinstance(parameters, dict) else 0
        retry_after = min(86400, max(0, retry_after)) if type(retry_after) is int else 0
        status = status if type(status) is int else 0
        messages = {
            400: tr("Telegram rechazó el chat o la imagen; revisa el ID y los permisos del bot"),
            401: tr("Token del bot de Telegram no válido"),
            403: tr("Telegram denegó el envío; inicia el bot o revisa sus permisos en el chat"),
            409: tr("El bot tiene un webhook u otra consulta activa; utiliza un bot dedicado"),
            429: tr("Telegram solicita esperar antes de reintentar"),
        }
        return TelegramError(messages.get(status, tr("Telegram no pudo completar la petición")), retry_after)

    def _request(self, method, data, content_type):
        request = Request(
            f"https://api.telegram.org/bot{self.token}/{method}",
            data=data,
            headers={"Content-Type": content_type},
            method="POST",
        )
        try:
            with self.transport(request, timeout=20) as response:
                payload = json.loads(response.read(1_000_001))
        except HTTPError as error:
            try:
                payload = json.loads(error.read(8192))
            except (ValueError, OSError):
                payload = {}
            if not isinstance(payload, dict):
                payload = {}
            raise self._failure(payload, error.code) from None
        except Exception:
            # Las URLs contienen el token: no persistir errores de urllib ni descripciones del proveedor.
            raise TelegramError(tr("No se puede conectar con Telegram o su respuesta no es válida")) from None
        if not isinstance(payload, dict):
            raise TelegramError(tr("Respuesta de Telegram no válida"))
        if payload.get("ok") is not True:
            raise self._failure(payload, payload.get("error_code"))
        return payload.get("result")

    def send_photo(self, chat_id, photo, caption):
        # Respetar el límite de 1024 unidades del pie de Telegram, incluidos pares sustitutos.
        caption = caption.encode("utf-16-le")[:1800].decode("utf-16-le", errors="ignore")
        data, content_type = multipart({"chat_id": chat_id, "caption": caption}, photo)
        result = self._request("sendPhoto", data, content_type)
        if not isinstance(result, dict) or not isinstance(result.get("message_id"), int):
            raise TelegramError(tr("Telegram no confirmó la entrega de la imagen"))

    def send_message(self, chat_id, text):
        text = text.encode("utf-16-le")[:7000].decode("utf-16-le", errors="ignore")
        result = self._request(
            "sendMessage", json.dumps({"chat_id": chat_id, "text": text}).encode(), "application/json"
        )
        if not isinstance(result, dict) or not isinstance(result.get("message_id"), int):
            raise TelegramError(tr("Telegram no confirmó la entrega del mensaje"))

    def recent_chats(self):
        updates = self._request("getUpdates", b'{"timeout":0,"limit":100}', "application/json")
        if not isinstance(updates, list):
            raise TelegramError(tr("Respuesta de chats de Telegram no válida"))
        chats = {}
        for update in updates:
            if not isinstance(update, dict):
                continue
            for key in ("message", "channel_post", "my_chat_member"):
                value = update.get(key)
                if not isinstance(value, dict):
                    continue
                chat = value.get("chat")
                if not isinstance(chat, dict):
                    continue
                if "id" in chat:
                    chats[str(chat["id"])] = {
                        "id": str(chat["id"]),
                        "name": chat.get("title") or chat.get("first_name") or tr("Chat"),
                    }
        return list(chats.values())
