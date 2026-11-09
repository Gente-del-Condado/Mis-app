"""Lectores RTSP opcionales: un último fotograma, inferencia compartida y prioridad SMTP."""


import threading
import time
from email.message import EmailMessage

import cv2

from .config import Settings
from .i18n import tr, service_language, translate_saved, use_language


def open_capture(url):
    return cv2.VideoCapture(
        url, cv2.CAP_FFMPEG,
        [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000, cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000],
    )


def resize(frame):
    height, width = frame.shape[:2]
    scale = min(1, 640 / max(height, width))
    return cv2.resize(frame, (max(1, round(width * scale)), max(1, round(height * scale))))


def motion_score(previous, frame):
    gray = cv2.GaussianBlur(cv2.cvtColor(cv2.resize(frame, (160, 120)), cv2.COLOR_BGR2GRAY), (5, 5), 0)
    if previous is None:
        return gray, 0.0
    changed = cv2.absdiff(previous, gray) > 25
    return gray, round(float(changed.mean()) * 100, 2)


def encode(frame, detections=()):
    preview = frame.copy()
    height, width = preview.shape[:2]
    for detection in detections:
        x1, y1, x2, y2 = [
            int(c * bound) for c, bound in zip(detection["box"], (width, height, width, height))
        ]
        cv2.rectangle(preview, (x1, y1), (x2, y2), (105, 223, 184), 2)
        cv2.putText(preview, tr("Persona {value0:.0%}", value0=detection['confidence']), (x1, max(18, y1)),
                    cv2.FONT_HERSHEY_SIMPLEX, .5, (105, 223, 184), 1)
    ok, jpeg = cv2.imencode(".jpg", preview, [cv2.IMWRITE_JPEG_QUALITY, 80])
    if not ok:
        raise ValueError(tr("No se puede codificar la imagen"))
    return jpeg.tobytes()


class CameraReader:
    def __init__(self, camera, capture_factory=open_capture):
        self.camera = camera.model_copy(deep=True)
        self.capture_factory = capture_factory
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.frame = None
        self.updated = 0
        self.state = "connecting"
        self.thread = threading.Thread(target=self.run, daemon=True, name=f"rtsp-{camera.id}")
        self.previous = None
        self.next_analysis = 0
        self.last_event = {}
        self.last_alert = 0
        self.jpeg = None
        self.analysis = {}

    def start(self):
        self.thread.start()

    def run(self):
        while not self.stop_event.is_set():
            capture = None
            try:
                capture = self.capture_factory(self.camera.url)
                if not capture.isOpened():
                    raise RuntimeError(tr("Cámara no disponible"))
                sampled = 0
                while not self.stop_event.is_set():
                    ok, frame = capture.read()
                    if not ok or frame is None:
                        raise RuntimeError(tr("Flujo interrumpido"))
                    # Leer el flujo continuamente; conservar como máximo un fotograma reducido.
                    now = time.monotonic()
                    if now - sampled < .25:
                        continue
                    small = resize(frame)
                    with self.lock:
                        self.frame, self.updated, self.state = small, time.time(), "connected"
                    sampled = now
            except Exception:
                # No exponer errores nativos ni URLs que puedan contener credenciales.
                with self.lock:
                    self.frame, self.jpeg, self.state = None, None, "reconnecting"
                    self.analysis = {}
                self.previous = None
            finally:
                if capture is not None:
                    try:
                        capture.release()
                    except Exception:
                        pass
            self.stop_event.wait(5)

    def snapshot(self):
        with self.lock:
            stale = time.time() - self.updated > 10
            return {
                "id": self.camera.id, "name": self.camera.name,
                "state": "reconnecting" if stale and self.state == "connected" else self.state,
                "updated": self.updated, **({} if stale else self.analysis),
            }


class StreamManager:
    def __init__(self, store, detector, capture_factory=open_capture):
        self.store, self.detector = store, detector
        self.capture_factory = capture_factory
        self.lock = threading.Lock()
        self.readers = {}
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        self.thread = threading.Thread(target=self.run, daemon=True, name="pivigia-streams")
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=15)

    def reconcile(self, settings):
        wanted = {c.id: c for c in settings.cameras if settings.rtsp_enabled and c.enabled}
        with self.lock:
            for key, reader in list(self.readers.items()):
                if key not in wanted or wanted[key] != reader.camera:
                    reader.stop_event.set()
                    # Conservar el lector que se detiene hasta que termine su lectura con tiempo límite.
                    if not reader.thread.is_alive():
                        del self.readers[key]
            for key, camera in wanted.items():
                if key not in self.readers and len(self.readers) < 8:
                    reader = CameraReader(camera, self.capture_factory)
                    self.readers[key] = reader
                    reader.start()
            return [r for r in self.readers.values() if not r.stop_event.is_set()]

    def run(self):
        try:
            while not self.stop_event.is_set():
                try:
                    settings = self.store.settings()
                    readers = self.reconcile(settings)
                    for reader in readers:
                        if self.stop_event.is_set():
                            break
                        # La cola SMTP tiene prioridad sobre la inferencia opcional de los flujos.
                        counts = self.store.stats()
                        if counts.get("queued", 0) or counts.get("processing", 0):
                            break
                        if time.monotonic() >= reader.next_analysis:
                            reader.next_analysis = time.monotonic() + reader.camera.interval
                            try:
                                self.analyze(reader, settings)
                            except Exception:
                                with reader.lock:
                                    reader.analysis = {"error": tr("No se pudo procesar la cámara")}
                except Exception:
                    # El fallo de una cámara no debe interrumpir la coordinación ni SMTP.
                    pass
                self.stop_event.wait(.25)
        finally:
            with self.lock:
                readers = list(self.readers.values())
            for reader in readers:
                reader.stop_event.set()
            deadline = time.monotonic() + 7
            for reader in readers:
                reader.thread.join(timeout=max(0, deadline - time.monotonic()))

    def analyze(self, reader, settings):
        with use_language(service_language(settings.language)):
            self._analyze(reader, settings)

    def _analyze(self, reader, settings):
        with reader.lock:
            if reader.frame is None or time.time() - reader.updated > 10:
                return
            frame, updated = reader.frame.copy(), reader.updated
        camera = reader.camera
        previous, score = motion_score(reader.previous, frame)
        reader.previous = previous
        moving = score >= camera.motion_percent
        raw = encode(frame)
        # Los límites de imágenes SMTP no se aplican a la vista RTSP reducida.
        limits = Settings(min_width=1, min_height=1)
        try:
            found, reason = self.detector.detect(raw, limits, camera.confidence)
            people = [d for d in found if d["category"] == "person"]
            error = tr("No se pudo analizar la imagen") if reason else ""
        except Exception:
            people, error = [], tr("Detector no disponible; comprueba el modelo")
        jpeg = encode(frame, people)
        now = time.time()
        with reader.lock:
            # Descartar resultados si falló la captura durante la inferencia.
            if reader.state != "connected":
                return
            reader.jpeg = jpeg
            reader.analysis = {
                "analyzed": now, "frame_time": updated, "motion": moving,
                "motion_score": score, "people": len(people), "detections": people,
                "error": error,
            }
        self.store.record_detections(found if not error else [], motion=moving)
        for kind, active in (("motion", moving), ("person", bool(people))):
            if active and now - reader.last_event.get(kind, 0) >= camera.cooldown:
                self.store.camera_event(camera, kind, people if kind == "person" else [])
                reader.last_event[kind] = now
        if not error and camera.alert_mailbox and now - reader.last_alert >= camera.cooldown:
            box = next((b for b in settings.mailboxes if b.address == camera.alert_mailbox and b.enabled), None)
            # La ausencia por sí sola no es un evento en una cámara continua.
            if not box:
                return
            active = moving if box.invert_detection else (people if box.forward_all else found)
            if active and box.should_notify(found, True, False):
                message = EmailMessage()
                subject = tr("Detección en vivo")
                if box.invert_detection:
                    subject = tr("Movimiento sin categorías marcadas")
                elif people and ("person" in box.categories or box.forward_all):
                    subject = tr("Persona detectada")
                message["Subject"] = subject + " · " + camera.name.replace("\r", "").replace("\n", "")
                message["From"] = "rtsp@pivigia.local"
                message["To"] = box.address
                message.set_content(tr("Detección en vivo de la cámara {value0}.", value0=camera.name))
                # Enviar el fotograma original; el trabajador dibujará las detecciones confirmadas.
                message.add_attachment(raw, maintype="image", subtype="jpeg", filename="camera.jpg")
                accepted = self.store.enqueue(box.address, "rtsp@pivigia.local", message.as_bytes(),
                                              settings.queue_limit)
                if accepted:
                    reader.last_alert = now
                else:
                    with reader.lock:
                        reader.analysis["error"] = tr("Cola llena; el aviso se intentará en el siguiente análisis")

    def status(self, settings):
        with self.lock:
            readers = dict(self.readers)
        result = []
        for camera in settings.cameras:
            reader = readers.get(camera.id)
            if not settings.rtsp_enabled or not camera.enabled:
                result.append({"id": camera.id, "name": camera.name, "state": "disabled"})
            elif reader and reader.camera == camera and not reader.stop_event.is_set():
                snapshot = reader.snapshot()
                if snapshot.get("error"):
                    snapshot["error"] = translate_saved(snapshot["error"])
                result.append(snapshot)
            else:
                result.append({"id": camera.id, "name": camera.name, "state": "connecting"})
        return result

    def preview(self, camera_id, settings):
        camera = next((c for c in settings.cameras if c.id == camera_id), None)
        if not camera or not settings.rtsp_enabled or not camera.enabled:
            return None
        with self.lock:
            reader = self.readers.get(camera_id)
        if not reader or reader.camera != camera or reader.stop_event.is_set():
            return None
        with reader.lock:
            if reader.frame is None or time.time() - reader.updated > 10:
                return None
            # Con SMTP ocupado, mostrar un fotograma reciente sin recuadros antiguos.
            if reader.analysis.get("frame_time", 0) < reader.updated - camera.interval * 2:
                return encode(reader.frame)
            return reader.jpeg or encode(reader.frame)
