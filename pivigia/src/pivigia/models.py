"""Catálogo de modelos fijados por hash y descargas asíncronas persistentes."""


import hashlib
import json
import shutil
import threading
import time
from pathlib import Path
from urllib.request import urlopen
from .i18n import N_, tr, translate_saved


ZOO = "https://media.githubusercontent.com/media/opencv/opencv_zoo/48b10fa505aeb51fbd127fc60a5c660040e823b7/models/object_detection_yolox/"
RELEASE = "https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/"
CATALOG = {
    "mobilenet": {"name": N_("MobileNet-SSD · ligero"), "size": 0, "builtin": True,
                  "description": N_("Incluido con PiVigia. Menor consumo; se conserva como alternativa de recuperación.")},
    "yolox_s": {"name": N_("YOLOX-S · intermedio"), "size": 35858002, "builtin": False,
                "url": ZOO + "object_detection_yolox_2022nov.onnx",
                "sha256": "c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063",
                "description": N_("Entrada de 640 px. Más trabajo que MobileNet; compara el resultado con tus fotos.")},
    "yolox_m": {"name": N_("YOLOX-M · grande"), "size": 101259744, "builtin": False,
                "url": RELEASE + "yolox_m.onnx",
                "sha256": "21ff6cfdeb53b013bac2249599e55f00bff3cfdfdab37ed7a4620818c1d15b3f",
                "description": N_("Mayor consumo de RAM y CPU. Preferible probar primero con fotos, no con varios flujos.")},
    "yolox_l": {"name": N_("YOLOX-L · muy grande"), "size": 216746733, "builtin": False,
                "url": RELEASE + "yolox_l.onnx",
                "sha256": "7860ae79de6c89a3c1eb72ae9a2756c0ccfbe04b7791bb5880afabd97855a411",
                "description": N_("Opción experimental y lenta en Raspberry Pi. Más tamaño no garantiza mejores detecciones.")},
}


class ModelManager:
    def __init__(self, directory, detector):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.detector = detector
        self.lock = threading.RLock()
        self.cancel = threading.Event()
        self.thread = None
        self.job = None
        self.active = "mobilenet"
        self.state_path = self.directory / "active.json"
        if self.state_path.exists():
            try:
                value = json.loads(self.state_path.read_text())["active"]
                self.spec(value)
                self.active = value
            except (ValueError, KeyError, TypeError):
                # Si falta el modelo guardado, informar del fallo sin seleccionar otro silenciosamente.
                raise ValueError(tr("Selección de modelo dañada en active.json")) from None
        for key in CATALOG:
            (self.directory / (key + ".part")).unlink(missing_ok=True)

    @staticmethod
    def spec(key):
        if key not in CATALOG:
            raise ValueError(tr("Modelo desconocido. Elige uno del catálogo."))
        return CATALOG[key]

    def path(self, key):
        self.spec(key)
        return self.directory / (key + ".onnx")

    def installed(self, key):
        spec = self.spec(key)
        if spec["builtin"]:
            return self.detector.ready_builtin()
        try:
            return self.path(key).stat().st_size == spec["size"]
        except OSError:
            return False

    def status(self):
        with self.lock:
            job = {**self.job, "message": translate_saved(self.job["message"])} if self.job else None
            return {"active": self.active, "download": job,
                    "free_bytes": shutil.disk_usage(self.directory).free,
                    "models": [{"id": key, **{k: tr(v) if k in {"name", "description"} else v
                                             for k, v in spec.items() if k != "url"},
                                "installed": self.installed(key), "active": key == self.active,
                                "license": tr("MobileNet-SSD (incluido)") if spec["builtin"] else "Apache-2.0"}
                               for key, spec in CATALOG.items()]}

    def start_download(self, key):
        spec = self.spec(key)
        if spec["builtin"]:
            raise ValueError(tr("El modelo ligero se instala al construir PiVigia."))
        with self.lock:
            if self.thread and self.thread.is_alive():
                raise ValueError(tr("Ya hay una descarga en curso. Espera o cancélala."))
            if self.installed(key):
                raise ValueError(tr("El modelo ya está descargado."))
            if shutil.disk_usage(self.directory).free < spec["size"] + 64 * 1024 * 1024:
                raise ValueError(tr("No hay espacio suficiente para descargar el modelo."))
            self.cancel.clear()
            self.job = {"id": key, "state": "downloading", "received": 0, "total": spec["size"],
                        "message": tr("Descargando; puedes seguir usando el panel.")}
            self.thread = threading.Thread(target=self._download, args=(key,), daemon=True)
            self.thread.start()
        return self.status()

    def _update(self, **values):
        with self.lock:
            self.job.update(values)

    def _download(self, key):
        spec = self.spec(key)
        temporary = self.directory / (key + ".part")
        try:
            digest = hashlib.sha256()
            received = 0
            started = time.monotonic()
            with urlopen(spec["url"], timeout=20) as response, temporary.open("wb") as output:
                while True:
                    if self.cancel.is_set():
                        raise InterruptedError
                    if time.monotonic() - started > 1800:
                        raise TimeoutError
                    block = response.read(256 * 1024)
                    if not block:
                        break
                    received += len(block)
                    if received > spec["size"]:
                        raise ValueError(tr("Tamaño incorrecto"))
                    output.write(block)
                    digest.update(block)
                    self._update(received=received)
            if received != spec["size"] or digest.hexdigest() != spec["sha256"]:
                raise ValueError(tr("Integridad incorrecta"))
            with self.lock:
                if self.cancel.is_set():
                    raise InterruptedError
                temporary.replace(self.path(key))
                self._update(state="complete", message=tr("Descarga verificada. Consulta la tarjeta para ver si el modelo está activo."))
        except InterruptedError:
            self._update(state="cancelled", message=tr("Descarga cancelada. Puedes iniciarla de nuevo."))
        except Exception:
            self._update(state="error", message=tr("No se pudo descargar y verificar. Comprueba Internet y espacio libre; puedes reintentar."))
        finally:
            temporary.unlink(missing_ok=True)

    def stop(self):
        self.cancel.set()
        if self.thread:
            self.thread.join(timeout=25)

    def activate(self, key):
        self.spec(key)
        # Los cambios bloquean primero el detector; la inferencia no necesita el bloqueo del gestor.
        with self.detector.lock, self.lock:
            if not self.installed(key):
                raise ValueError(tr("Descarga el modelo antes de activarlo."))
            self.detector.load_model(key)
            temporary = self.state_path.with_suffix(".tmp")
            temporary.write_text(json.dumps({"active": key}))
            temporary.replace(self.state_path)
            self.active = key
        return self.status()

    def delete(self, key):
        spec = self.spec(key)
        with self.detector.lock, self.lock:
            if spec["builtin"]:
                raise ValueError(tr("El modelo ligero está incluido en la aplicación y se conserva para recuperación."))
            if key == self.active:
                raise ValueError(tr("Activa otro modelo antes de eliminar este."))
            if self.thread and self.thread.is_alive() and self.job["id"] == key:
                raise ValueError(tr("Cancela la descarga y espera a que termine antes de eliminar."))
            self.detector.unload_model(key)
            self.path(key).unlink(missing_ok=True)
            if self.job and self.job["id"] == key:
                self.job = None
        return self.status()
