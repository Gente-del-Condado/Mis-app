"""Inferencia local serializada y validación de imágenes antes de cargar OpenCV."""
import io
import os
import threading
from pathlib import Path

# Los diagnósticos nativos de FFmpeg pueden incluir URLs de cámaras con contraseñas.
os.environ.setdefault("OPENCV_FFMPEG_LOGLEVEL", "-8")
os.environ.setdefault("OPENCV_LOG_LEVEL", "SILENT")

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from .models import ModelManager
from .config import IMAGE_FORMATS
from .i18n import tr

Image.MAX_IMAGE_PIXELS = 16_777_216
LABELS = (
    "background",
    "aeroplane",
    "bicycle",
    "bird",
    "boat",
    "bottle",
    "bus",
    "car",
    "cat",
    "chair",
    "cow",
    "diningtable",
    "dog",
    "horse",
    "motorbike",
    "person",
    "pottedplant",
    "sheep",
    "sofa",
    "train",
    "tvmonitor",
)
ANIMALS = {"bird", "cat", "cow", "dog", "horse", "sheep"}


class Detector:
    def __init__(self, model_directory=None):
        self.net = None
        self.loaded_model = "mobilenet"
        self.lock = threading.RLock()
        self.directory = Path(os.environ.get("PIVIGIA_MODELS", "models"))
        self.models = ModelManager(model_directory, self) if model_directory is not None else None

    def ready(self):
        return self.models.installed(self.models.active) if self.models else self.ready_builtin()

    def ready_builtin(self):
        return all((self.directory / p).is_file() for p in ("deploy.prototxt", "mobilenet.caffemodel"))

    def detect(self, content, settings, threshold, model=None):
        if len(content) > settings.max_image_bytes:
            return [], tr("Imagen supera el límite de bytes")
        try:
            with Image.open(io.BytesIO(content), formats=IMAGE_FORMATS) as source:
                width, height = source.size
                if width * height > Image.MAX_IMAGE_PIXELS:
                    return [], tr("Imagen supera el límite de 16 megapíxeles")
                if not (
                    settings.min_width <= width <= settings.max_width
                    and settings.min_height <= height <= settings.max_height
                ):
                    return [], tr("Dimensiones fuera de límites: {width}×{height}", width=width, height=height)
                image = np.array(ImageOps.exif_transpose(source).convert("RGB"))
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
            return [], tr("Imagen no válida")
        with self.lock:
            key = model or (self.models.active if self.models else "mobilenet")
            self.load_model(key)
            return self._infer(image, threshold) if key == "mobilenet" else self._infer_yolox(image, threshold, key)

    def unload_model(self, key):
        if self.loaded_model == key:
            self.net = None

    def load_model(self, key):
        if key != "mobilenet" and (not self.models or not self.models.installed(key)):
            raise ValueError(tr("Descarga el modelo antes de usarlo."))
        if self.net is not None and self.loaded_model == key:
            return
        if key == "mobilenet" and not self.ready_builtin():
            raise RuntimeError(tr("Modelo ligero ausente"))
        # Liberar la red anterior antes de cargar otra para limitar el consumo de memoria.
        self.net = None
        cv2.setNumThreads(int(os.environ.get("PIVIGIA_INFERENCE_THREADS", "1")))
        self.net = (cv2.dnn.readNetFromCaffe(str(self.directory / "deploy.prototxt"),
                                          str(self.directory / "mobilenet.caffemodel"))
                    if key == "mobilenet" else cv2.dnn.readNetFromONNX(str(self.models.path(key))))
        self.loaded_model = key

    def _infer_yolox(self, image, threshold, key):
        height, width = image.shape[:2]
        ratio = min(640 / height, 640 / width)
        padded = np.full((640, 640, 3), 114, dtype=np.float32)
        resized_w, resized_h = max(1, int(width * ratio)), max(1, int(height * ratio))
        padded[:resized_h, :resized_w] = cv2.resize(image, (resized_w, resized_h))
        # La versión fijada de Megvii normaliza RGB; OpenCV Zoo S recibe RGB sin esa normalización.
        if key in {"yolox_m", "yolox_l"}:
            padded = (padded / 255 - np.array([.485, .456, .406], dtype=np.float32)) / np.array(
                [.229, .224, .225], dtype=np.float32)
        self.net.setInput(np.ascontiguousarray(padded.transpose(2, 0, 1)[None]))
        rows = self.net.forward().reshape(-1, 85).copy()
        return decode_yolox(rows, width, height, ratio, threshold), None

    def _infer(self, image, threshold):
        if self.net is None:
            if not self.ready_builtin():
                raise RuntimeError(tr("Modelo ausente: ejecuta scripts/download_model.py"))
            cv2.setNumThreads(int(os.environ.get("PIVIGIA_INFERENCE_THREADS", "1")))
            self.net = cv2.dnn.readNetFromCaffe(
                str(self.directory / "deploy.prototxt"), str(self.directory / "mobilenet.caffemodel")
            )
        # OpenCV interpreta una media escalar como (valor, 0, 0); hay que indicar los tres canales.
        blob = cv2.dnn.blobFromImage(
            cv2.cvtColor(image, cv2.COLOR_RGB2BGR), 0.007843, (300, 300), (127.5, 127.5, 127.5)
        )
        self.net.setInput(blob)
        rows = self.net.forward().reshape(-1, 7)
        detections = []
        for row in rows:
            index = int(row[1])
            if index < 0 or index >= len(LABELS) or row[2] < threshold:
                continue
            label = LABELS[index]
            category = "animal" if label in ANIMALS else label
            if category in {"animal", "car", "person"}:
                detections.append(
                    {
                        "category": category,
                        "label": label,
                        "confidence": round(float(row[2]), 3),
                        "box": [round(float(c), 4) for c in np.clip(row[3:7], 0, 1)],
                    }
                )
        # SSD filtra por especie; unificar etiquetas animales duplicadas sobre un mismo objeto.
        selected = []
        for detection in sorted(detections, key=lambda d: d["confidence"], reverse=True):
            if not any(
                detection["category"] == previous["category"]
                and box_iou(detection["box"], previous["box"]) > 0.7
                for previous in selected
            ):
                selected.append(detection)
        return selected, None


COCO_TARGETS = {0: "person", 2: "car", 14: "bird", 15: "cat", 16: "dog", 17: "horse",
                18: "sheep", 19: "cow", 20: "elephant", 21: "bear", 22: "zebra", 23: "giraffe"}


def decode_yolox(rows, width, height, ratio, threshold):
    grids, strides = [], []
    for stride in (8, 16, 32):
        y, x = np.mgrid[:640 // stride, :640 // stride]
        grids.append(np.stack((x, y), axis=-1).reshape(-1, 2))
        strides.append(np.full((x.size, 1), stride))
    grid, scale = np.concatenate(grids), np.concatenate(strides)
    if rows.shape != (8400, 85):
        raise ValueError(tr("Salida de modelo inesperada"))
    centers = (rows[:, :2] + grid) * scale
    sizes = np.exp(np.clip(rows[:, 2:4], -20, 20)) * scale
    scores = rows[:, 4:5] * rows[:, 5:]
    classes = scores.argmax(axis=1)
    confidence = scores.max(axis=1)
    candidates = []
    for index in np.flatnonzero(np.isfinite(confidence) & (confidence >= threshold)):
        label = COCO_TARGETS.get(int(classes[index]))
        if label is None:
            continue
        box = np.concatenate((centers[index] - sizes[index] / 2, centers[index] + sizes[index] / 2))
        box = np.clip(box / ratio / np.array([width, height, width, height]), 0, 1)
        if not np.all(np.isfinite(box)) or box[2] <= box[0] or box[3] <= box[1]:
            continue
        candidates.append({"category": label if label in {"person", "car"} else "animal", "label": label,
                           "confidence": round(float(confidence[index]), 3), "box": box.round(4).tolist()})
    selected = []
    for detection in sorted(candidates, key=lambda d: d["confidence"], reverse=True):
        if not any(detection["category"] == previous["category"]
                   and box_iou(detection["box"], previous["box"]) > .45 for previous in selected):
            selected.append(detection)
    return selected


def box_iou(a, b):
    intersection = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    area_a = max(0, a[2] - a[0]) * max(0, a[3] - a[1])
    area_b = max(0, b[2] - b[0]) * max(0, b[3] - b[1])
    return intersection / max(area_a + area_b - intersection, 1e-9)
