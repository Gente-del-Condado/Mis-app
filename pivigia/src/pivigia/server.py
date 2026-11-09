"""Ajustes de arranque separados de las reglas; sus cambios requieren reiniciar."""


import ipaddress
import os

from pydantic import BaseModel, Field, field_validator, model_validator
from .i18n import tr


ENV_FIELDS = {
    "web_bind": "PIVIGIA_WEB_BIND", "web_port": "PIVIGIA_WEB_PORT",
    "smtp_bind": "PIVIGIA_SMTP_BIND", "smtp_port": "PIVIGIA_SMTP_PORT",
    "trusted_networks": "PIVIGIA_TRUSTED_NETWORKS", "allow_plain_auth": "PIVIGIA_ALLOW_PLAIN_AUTH",
    "tls_cert": "PIVIGIA_TLS_CERT", "tls_key": "PIVIGIA_TLS_KEY",
}


class ServerSettings(BaseModel):
    web_bind: str = "0.0.0.0"
    web_port: int = Field(default=8099, ge=1024, le=65535)
    smtp_bind: str = "0.0.0.0"
    smtp_port: int = Field(default=2525, ge=1024, le=65535)
    trusted_networks: str = Field(default="", max_length=2000)
    allow_plain_auth: bool = False
    tls_cert: str = Field(default="", max_length=1000)
    tls_key: str = Field(default="", max_length=1000)

    @field_validator("web_bind", "smtp_bind")
    @classmethod
    def bind_valid(cls, value):
        return str(ipaddress.ip_address(value.strip()))

    @field_validator("trusted_networks")
    @classmethod
    def networks_valid(cls, value):
        return ",".join(str(ipaddress.ip_network(item.strip())) for item in value.split(",") if item.strip())

    @model_validator(mode="after")
    def valid(self):
        if self.web_port == self.smtp_port:
            raise ValueError(tr("El panel y SMTP necesitan puertos diferentes"))
        if bool(self.tls_cert) != bool(self.tls_key):
            raise ValueError(tr("Configura tanto el certificado como su clave"))
        for path in (self.tls_cert, self.tls_key):
            if path and (not path.startswith("/") or any(ord(c) < 32 for c in path)):
                raise ValueError(tr("Usa rutas absolutas para el certificado y su clave"))
        return self

    def effective(self, environ=None):
        environ = os.environ if environ is None else environ
        values = self.model_dump()
        for field, variable in ENV_FIELDS.items():
            if variable in environ:
                value = environ[variable]
                values[field] = value == "1" if field == "allow_plain_auth" else value
        return ServerSettings.model_validate(values)


def deployment():
    value = os.environ.get("PIVIGIA_DEPLOYMENT", "local")
    return value if value in {"local", "docker", "homeassistant", "yunohost"} else "local"
