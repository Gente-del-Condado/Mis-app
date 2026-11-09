"""Identidad del panel mediante token o el proxy Ingress autorizado de Home Assistant."""


import hmac
import ipaddress
import os
from dataclasses import dataclass

from .server import deployment
from .i18n import tr

SUPERVISOR_IP = ipaddress.ip_address("172.30.32.2")
READ_PATHS = {"/api/status", "/api/events", "/api/cameras", "/api/auth/session"}


@dataclass(frozen=True)
class Identity:
    provider: str
    role: str
    user_id: str
    name: str

    @property
    def admin(self):
        return self.role == "admin"

    def public(self):
        return {"provider": self.provider, "role": self.role, "user_id": self.user_id,
                "name": self.name, "can_admin": self.admin}


class AuthPolicy:
    def __init__(self):
        self.homeassistant = deployment() == "homeassistant"
        self.mode = os.environ.get("PIVIGIA_PANEL_LOGIN", "both") if self.homeassistant else "token"
        if self.mode not in {"token", "homeassistant", "both"}:
            raise ValueError(tr("Método de acceso de PiVigia no válido"))

    @property
    def token_login(self):
        return self.mode in {"token", "both"}

    @property
    def ha_login(self):
        return self.homeassistant and self.mode in {"homeassistant", "both"}

    def options(self):
        return {"mode": self.mode, "token_login": self.token_login, "homeassistant_login": self.ha_login,
                "homeassistant": self.homeassistant}

    @staticmethod
    def trusted_ingress(request):
        if not request.client:
            return False
        try:
            peer = ipaddress.ip_address(request.client.host)
            if isinstance(peer, ipaddress.IPv6Address) and peer.ipv4_mapped:
                peer = peer.ipv4_mapped
            return peer == SUPERVISOR_IP
        except ValueError:
            return False

    def identify(self, request, token):
        if self.ha_login and self.trusted_ingress(request):
            user_id = request.headers.get("x-remote-user-id", "").strip()
            if user_id:
                groups = {group.strip() for group in request.headers.get("x-remote-user-groups", "").split(",")}
                if "system-admin" in groups:
                    role = "admin"
                elif groups & {"system-users", "system-read-only"}:
                    role = "viewer"
                else:
                    # Un Supervisor sin información de grupos no puede conceder permisos administrativos.
                    return None
                name = (request.headers.get("x-remote-user-display-name")
                        or request.headers.get("x-remote-user-name") or tr("Usuario de Home Assistant"))
                return Identity("homeassistant", role, user_id[:128], name[:160])
        supplied = request.headers.get("authorization", "").removeprefix("Bearer ")
        if supplied and hmac.compare_digest(supplied.encode(), token.encode()):
            if self.token_login:
                return Identity("token", "admin", "token", tr("Administrador con token"))
            # Conservar la consulta de sensores cuando el panel solo admite sesión de Home Assistant.
            return Identity("integration_token", "service", "integration", tr("Integración de sensores"))
        return None

    @staticmethod
    def permits(identity, method, path):
        if identity.role == "service":
            return method == "GET" and path == "/api/status"
        if identity.admin:
            return True
        return method == "GET" and (
            path in READ_PATHS or (path.startswith("/api/cameras/") and path.endswith("/preview"))
        )
