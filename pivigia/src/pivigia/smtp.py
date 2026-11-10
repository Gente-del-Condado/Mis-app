"""Entrada SMTP autenticada o por IP autorizada; valida antes de admitir la cola."""
import ipaddress
import ssl

from aiosmtpd.controller import Controller
from aiosmtpd.smtp import AuthResult, LoginPassword

from .config import check_password
from .server import ServerSettings
from .i18n import tr

MAX_MESSAGE = 15_000_000


class Handler:
    def __init__(self, store, server_settings=None):
        self.store = store
        settings = server_settings or ServerSettings().effective()
        self.trusted = [
            ipaddress.ip_network(x.strip())
            for x in settings.trusted_networks.split(",")
            if x.strip()
        ]

    def is_trusted(self, session):
        return any(ipaddress.ip_address(session.peer[0]) in network for network in self.trusted)

    def authenticate(self, server, session, envelope, mechanism, auth_data):
        if not isinstance(auth_data, LoginPassword):
            return AuthResult(success=False, handled=False)
        try:
            username = auth_data.login.decode().lower()
            password = auth_data.password.decode()
            box = next(
                (b for b in self.store.settings().mailboxes if b.address == username and b.enabled), None
            )
            valid = box is not None and check_password(password, box.password)
        except (UnicodeError, ValueError):
            valid = False
        return AuthResult(success=valid, handled=False, auth_data=username if valid else None)

    async def handle_RCPT(self, server, session, envelope, address, rcpt_options):
        box = next(
            (b for b in self.store.settings().mailboxes if b.address == address.lower() and b.enabled), None
        )
        if box is None:
            return tr("550 Buzón no disponible")
        if not self.is_trusted(session) and (not session.authenticated or session.auth_data != box.address):
            return tr("530 Autenticación requerida para este buzón")
        if envelope.rcpt_tos:
            return tr("452 Un único buzón por mensaje; envía una copia por buzón")
        envelope.rcpt_tos.append(box.address)
        return "250 OK"

    async def handle_DATA(self, server, session, envelope):
        if len(envelope.original_content) > MAX_MESSAGE:
            return tr("552 Mensaje demasiado grande")
        if not envelope.rcpt_tos:
            return tr("554 Falta destinatario")
        accepted = self.store.enqueue(
            envelope.rcpt_tos[0],
            envelope.mail_from,
            envelope.original_content,
            self.store.settings().queue_limit,
        )
        return tr("250 Encolado en PiVigia") if accepted else tr("452 Cola llena; reintenta más tarde")


def start_smtp(store, server_settings=None):
    settings = server_settings or store.server_settings().effective()
    handler = Handler(store, settings)
    cert, key = settings.tls_cert, settings.tls_key
    context = None
    if cert and key:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(cert, key)
    controller = Controller(
        handler,
        hostname=settings.smtp_bind,
        port=settings.smtp_port,
        data_size_limit=MAX_MESSAGE,
        authenticator=handler.authenticate,
        auth_require_tls=not settings.allow_plain_auth,
        tls_context=context,
        decode_data=False,
    )
    controller.start()
    return controller
