"""Contratos de configuración, reglas por correo y credenciales de buzones."""
import hashlib
import hmac
import os
import re
import secrets
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, model_validator, field_validator
from .i18n import tr, match_language


class Mailbox(BaseModel):
    address: str
    password: str = Field(min_length=8, max_length=200)
    destinations: list[str] = Field(default_factory=list, max_length=20)
    telegram_chat_ids: list[str] = Field(default_factory=list, max_length=10)
    categories: list[str] = Field(default_factory=lambda: ["person", "car", "animal"])
    confidence: float = Field(default=0.5, ge=0.1, le=1)
    enabled: bool = True
    forward_all: bool = False

    invert_detection: bool = False

    @model_validator(mode="after")
    def check_inverse_rule(self):
        if self.invert_detection and (self.forward_all or not self.categories):
            raise ValueError(tr("Para invertir la detección, selecciona alguna categoría y desactiva el reenvío de todos los mensajes."))
        return self

    def should_notify(self, detections, valid_images, skipped):
        """La ausencia solo es válida con análisis completo; decide sobre todo el correo."""
        if self.forward_all:
            return True
        matched = any(d["category"] in self.categories for d in detections)
        if self.invert_detection:
            return bool(valid_images) and not skipped and not matched
        return matched

    @field_validator("address")
    @classmethod
    def address_valid(cls, value):
        return email_address(value)

    @field_validator("destinations")
    @classmethod
    def destinations_valid(cls, values):
        return list(dict.fromkeys(email_address(v) for v in values))

    @field_validator("telegram_chat_ids")
    @classmethod
    def chats_valid(cls, values):
        values = [value.strip() for value in values]
        if any(not re.fullmatch(r"(?:-?[1-9][0-9]{0,19}|@[A-Za-z][A-Za-z0-9_]{4,31})", v) for v in values):
            raise ValueError(tr("Indica IDs de chat numéricos o @nombre_del_canal"))
        return list(dict.fromkeys(values))

    @field_validator("categories")
    @classmethod
    def categories_valid(cls, values):
        if not set(values) <= {"person", "car", "animal"}:
            raise ValueError(tr("Categorías: person, car, animal"))
        return values


def email_address(value):
    value = value.strip().lower()
    if (
        not value.isascii()
        or len(value) > 254
        or value.count("@") != 1
        or any(c.isspace() or ord(c) < 32 for c in value)
    ):
        raise ValueError(tr("Dirección de correo no válida"))
    if not all(value.split("@")) or any(c in value for c in '<>,;"\\'):
        raise ValueError(tr("Dirección de correo no válida"))
    return value


class Camera(BaseModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,48}$")
    name: str = Field(min_length=1, max_length=80)
    url: str = Field(min_length=1, max_length=2048)
    enabled: bool = True
    interval: float = Field(default=2, ge=1, le=60)
    confidence: float = Field(default=0.5, ge=0.1, le=1)
    motion_percent: float = Field(default=2, ge=0.1, le=100)
    cooldown: int = Field(default=60, ge=10, le=3600)
    alert_mailbox: str = ""

    @field_validator("url")
    @classmethod
    def rtsp_url(cls, value):
        value = value.strip()
        if value == "********":
            return value
        parsed = urlsplit(value)
        if (parsed.scheme not in {"rtsp", "rtsps"} or not parsed.hostname
                or any(c.isspace() or ord(c) < 32 for c in value) or parsed.fragment):
            raise ValueError(tr("Indica una URL RTSP válida"))
        _ = parsed.port  # Validar también puertos mal formados.
        return value

    @field_validator("alert_mailbox")
    @classmethod
    def mailbox_valid(cls, value):
        return email_address(value) if value else ""


class Settings(BaseModel):
    language: str = "es"

    @field_validator("language")
    @classmethod
    def language_valid(cls, value):
        language = match_language(value)
        if language is None:
            raise ValueError(tr("Idioma no disponible"))
        return language

    min_width: int = Field(default=160, ge=1, le=12000)
    min_height: int = Field(default=120, ge=1, le=12000)
    max_width: int = Field(default=4096, ge=1, le=12000)
    max_height: int = Field(default=4096, ge=1, le=12000)
    max_image_bytes: int = Field(default=5_000_000, ge=1024, le=20_000_000)
    max_images: int = Field(default=10, ge=1, le=30)
    retention_days: int = Field(default=7, ge=1, le=90)
    queue_limit: int = Field(default=200, ge=1, le=1000)
    smtp_host: str = ""
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_security: str = "starttls"
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    telegram_enabled: bool = False
    telegram_bot_token: str = Field(default="", max_length=160)

    @field_validator("telegram_bot_token")
    @classmethod
    def bot_token_valid(cls, value):
        value = value.strip()
        if value and value != "********" and not re.fullmatch(r"[0-9]{1,20}:[A-Za-z0-9_-]{20,128}", value):
            raise ValueError(tr("Token de bot de Telegram no válido"))
        return value

    mailboxes: list[Mailbox] = Field(default_factory=list, max_length=50)
    rtsp_enabled: bool = False
    cameras: list[Camera] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def valid(self):
        if self.min_width > self.max_width or self.min_height > self.max_height:
            raise ValueError(tr("El mínimo debe ser menor o igual que el máximo"))
        if self.smtp_security not in {"starttls", "ssl", "plain"}:
            raise ValueError(tr("Seguridad SMTP no válida"))
        if self.telegram_enabled and not self.telegram_bot_token:
            raise ValueError(tr("Indica el token del bot antes de activar Telegram"))
        if self.smtp_from:
            self.smtp_from = email_address(self.smtp_from)
        if len({b.address for b in self.mailboxes}) != len(self.mailboxes):
            raise ValueError(tr("Hay buzones duplicados"))
        if len({camera.id for camera in self.cameras}) != len(self.cameras):
            raise ValueError(tr("Hay cámaras duplicadas"))
        addresses = {box.address for box in self.mailboxes}
        if any(camera.alert_mailbox and camera.alert_mailbox not in addresses for camera in self.cameras):
            raise ValueError(tr("El buzón de avisos de la cámara no existe"))
        for value in (self.smtp_host, self.smtp_username, self.smtp_from):
            if "\n" in value or "\r" in value:
                raise ValueError(tr("Saltos de línea no permitidos"))
        return self


def digest(password, salt):
    return hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1).hex()


def check_password(password, encoded):
    salt, expected = encoded.split(":")
    return hmac.compare_digest(digest(password, bytes.fromhex(salt)), expected)


def hash_password(password):
    salt = secrets.token_bytes(16)
    return salt.hex() + ":" + digest(password, salt)


def data_dir():
    path = Path(os.environ.get("PIVIGIA_DATA", "data"))
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path
