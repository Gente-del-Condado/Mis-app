"""Procesa la cola y persiste entregas parciales para reintentar destinos pendientes."""
import json
import logging
import smtplib
import ssl
import threading
import time
from contextlib import ExitStack
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import formatdate, make_msgid

from .detector import Detector
from .notifications import alert_text, prepare_images, set_email_content
from .telegram import TelegramClient
from .i18n import tr, service_language, use_language

log = logging.getLogger(__name__)


class ShutdownRequested(Exception):
    pass


class DeliveryError(RuntimeError):
    def __init__(self, message, retry_after=0):
        super().__init__(message)
        self.retry_after = retry_after


class Worker:
    def __init__(self, store, detector=None):
        self.store = store
        self.detector = detector or Detector(store.path / "models")
        self.stop_event = threading.Event()
        self.thread = None
        self.telegram_last_sent = {}

    def start(self):
        self.thread = threading.Thread(target=self.run, daemon=True, name="pivigia-worker")
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=35)

    def run(self):
        ticks = 0
        while not self.stop_event.is_set():
            try:
                job = self.store.claim()
                if job:
                    self.process(job)
                else:
                    self.stop_event.wait(1)
                ticks += 1
                if ticks % 60 == 0:
                    self.store.cleanup(self.store.settings().retention_days)
            except Exception:
                log.exception(tr("Error del trabajador"))
                self.stop_event.wait(2)

    def process(self, job):
        # El contexto de idioma se libera incluso cuando falla la carga de ajustes.
        with ExitStack() as scope:
            self._process(job, scope)

    def _process(self, job, scope):
        settings = None
        try:
            settings = self.store.settings()
            scope.enter_context(use_language(service_language(settings.language)))
            mailbox = next((b for b in settings.mailboxes if b.address == job["mailbox"] and b.enabled), None)
            if mailbox is None:
                self.store.update(
                    job["id"], status="discarded", error=tr("Buzón desactivado o eliminado"), raw=None
                )
                return
            message = BytesParser(policy=policy.default).parsebytes(job["raw"])
            if message.get("X-PiVigia"):
                self.store.update(job["id"], status="discarded", error=tr("Bucle de reenvío evitado"), raw=None)
                return
            result = json.loads(job["result"])
            if result.get("schema") != 2:
                detections, skipped, valid_images = [], [], []
                count = 0
                for part in message.walk():
                    if part.get_content_maintype() != "image":
                        continue
                    count += 1
                    if count > settings.max_images:
                        skipped.append(tr("Se alcanzó el límite de imágenes por correo"))
                        break
                    found, reason = self.detector.detect(
                        part.get_payload(decode=True) or b"", settings, mailbox.confidence
                    )
                    detections.extend({**d, "image": count} for d in found)
                    if not reason:
                        valid_images.append(count)
                    if reason:
                        skipped.append(reason)
                result = {
                    "analyzed": True,
                    "schema": 2,
                    "valid_images": valid_images,
                    "images": min(count, settings.max_images),
                    "detections": detections,
                    "skipped": skipped,
                }
                self.store.update(job["id"], result=json.dumps(result))
            matches = [d for d in result["detections"] if d["category"] in mailbox.categories]
            if not mailbox.should_notify(result["detections"], result["valid_images"], result["skipped"]):
                self.store.update(job["id"], status="filtered", raw=None)
                return
            chats = mailbox.telegram_chat_ids if settings.telegram_enabled else []
            if not mailbox.destinations and not chats:
                self.store.update(
                    job["id"], status="filtered", error=tr("Sin destinos de correo o Telegram"), raw=None
                )
                return
            images = prepare_images(message, result, mailbox)
            delivered = json.loads(job["delivered"])
            failures, retry_after = [], 0

            def deliver(key, callback, channel):
                nonlocal retry_after
                if key in delivered:
                    return
                if self.stop_event.is_set():
                    raise ShutdownRequested()
                try:
                    callback()
                except ShutdownRequested:
                    raise
                except Exception as error:
                    failures.append(f"{channel}: {error}")
                    retry_after = max(retry_after, getattr(error, "retry_after", 0))
                    return
                delivered.append(key)
                self.store.update(job["id"], delivered=json.dumps(delivered))

            for destination in mailbox.destinations:
                deliver(
                    destination,
                    lambda: self.forward(settings, destination, message, job, result, images),
                    tr("Correo {destination}", destination=destination),
                )
            if chats:
                client = TelegramClient(settings.telegram_bot_token)
                bot_id = settings.telegram_bot_token.split(":")[0]
                for chat in chats:
                    for asset in images or [None]:
                        index = asset["index"] if asset else "text"
                        key = f"telegram:{bot_id}:{chat}:{index}"
                        caption = alert_text(
                            job,
                            message,
                            asset["detections"] if asset else matches,
                            asset["index"] if asset else None,
                            inverse=mailbox.invert_detection,
                        )
                        if not asset:
                            caption += tr("\nNo hay imágenes aptas para adjuntar.")
                        deliver(
                            key,
                            lambda: self.send_telegram(client, bot_id, chat, asset, caption),
                            tr("Telegram {chat}", chat=chat),
                        )
            if failures:
                raise DeliveryError("; ".join(failures), retry_after)
            self.store.update(job["id"], status="sent", raw=None, error="")
        except ShutdownRequested:
            self.store.update(job["id"], status="queued", next_try=0)
        except Exception as error:
            attempts = job["attempts"] + 1
            description = f"{type(error).__name__}: {error}"
            if settings:
                for secret in (settings.smtp_password, settings.telegram_bot_token):
                    if secret:
                        description = description.replace(secret, tr("[oculto]"))
            self.store.update(
                job["id"],
                attempts=attempts,
                status="failed" if attempts >= 5 else "queued",
                next_try=time.time() + max(min(3600, 30 * 2**attempts), getattr(error, "retry_after", 0)),
                error=description[:400],
            )
            log.warning(tr("Trabajo %s pendiente/fallido: %s"), job["id"], type(error).__name__)

    def send_telegram(self, client, bot_id, chat, asset, caption):
        destination = (bot_id, chat)
        interval = 3.1 if chat.startswith("-") else 1.05
        delay = max(0, self.telegram_last_sent.get(destination, 0) + interval - time.monotonic())
        if self.stop_event.wait(delay):
            raise ShutdownRequested()
        if asset:
            client.send_photo(chat, asset["content"], caption)
        else:
            client.send_message(chat, caption)
        self.telegram_last_sent[destination] = time.monotonic()

    @staticmethod
    def forward(settings, destination, original, job, result, images=None):
        with use_language(service_language(settings.language)):
            Worker._forward(settings, destination, original, job, result, images)

    @staticmethod
    def _forward(settings, destination, original, job, result, images=None):
        if not settings.smtp_host or not settings.smtp_from:
            raise RuntimeError(tr("Configura el servidor SMTP de salida y el remitente"))
        message = EmailMessage()
        message["From"] = settings.smtp_from
        message["To"] = destination
        subject = str(original.get("Subject", tr("(sin asunto)"))).replace("\r", "").replace("\n", "")
        message["Subject"] = "[PiVigia] " + subject[:200]
        message["Date"] = formatdate(localtime=False)
        message["Message-ID"] = make_msgid(idstring=f"pivigia-{job['id']}")
        message["X-PiVigia"] = "1"
        mailbox = next(b for b in settings.mailboxes if b.address == job["mailbox"])
        if images is None:
            images = prepare_images(original, result, mailbox)
        set_email_content(message, job, original, result, mailbox, images)
        Worker.send_email(settings, destination, message)

    @staticmethod
    def send_email(settings, destination, message):
        if not settings.smtp_host or not settings.smtp_from:
            raise RuntimeError(tr("Configura el servidor SMTP de salida y el remitente"))
        context = ssl.create_default_context()
        if settings.smtp_security == "ssl":
            smtp = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=20, context=context)
        else:
            smtp = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20)
        with smtp:
            if settings.smtp_security == "starttls":
                smtp.starttls(context=context)
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message, from_addr=settings.smtp_from, to_addrs=[destination])
