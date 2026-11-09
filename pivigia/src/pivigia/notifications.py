"""Contenido común de las alertas: resultados e imágenes asociadas."""


import io
import math
from html import escape

from PIL import Image, ImageDraw, ImageFont, ImageOps
from .i18n import N_, tr

LABELS = {
    "person": N_("Persona"),
    "car": N_("Coche"),
    "bird": N_("Ave"),
    "cat": N_("Gato"),
    "cow": N_("Vaca"),
    "dog": N_("Perro"),
    "horse": N_("Caballo"),
    "sheep": N_("Oveja"),
    "elephant": N_("Elefante"),
    "bear": N_("Oso"),
    "zebra": N_("Cebra"),
    "giraffe": N_("Jirafa"),
    "animal": N_("Animal"),
}


def detection_text(detection):
    name = tr(LABELS[detection["label"]]) if detection["label"] in LABELS else detection["label"]
    return f"{name} — {detection['confidence']:.0%}"


def matching_detections(result, mailbox):
    return [d for d in result["detections"] if d["category"] in mailbox.categories]


def alert_text(job, original, detections, image_index=None, *, inverse=False):
    subject = str(original.get("Subject", tr("(sin asunto)"))).replace("\r", "").replace("\n", "")[:140]
    lines = [tr("PiVigia · alerta #{value0}", value0=job['id']), tr("Buzón: {value0}", value0=job['mailbox']), tr("Asunto: {subject}", subject=subject)]
    if image_index is not None:
        lines.append(tr("Imagen {image_index}", image_index=image_index))
    lines.append("")
    lines.extend(tr("Imagen {value0}: {value1}", value0=d.get('image', 1), value1=detection_text(d)) for d in detections)
    if not detections:
        lines.append(tr("Aviso por ausencia de las categorías seleccionadas.") if inverse else
                     tr("Sin detecciones de las categorías seleccionadas (reenvío de todos los mensajes)."))
    return "\n".join(lines)


def prepare_images(original, result, mailbox):
    """Solo genera vistas de imágenes validadas y relevantes para las reglas del buzón."""
    wanted = set(result["valid_images"])
    detections = matching_detections(result, mailbox)
    if not (mailbox.forward_all or mailbox.invert_detection):
        wanted &= {d["image"] for d in detections}
    images = []
    index = 0
    for part in original.walk():
        if part.get_content_maintype() != "image":
            continue
        index += 1
        if index not in wanted:
            continue
        content = part.get_payload(decode=True) or b""
        with Image.open(io.BytesIO(content)) as source:
            if source.width * source.height > Image.MAX_IMAGE_PIXELS:
                raise ValueError(tr("Imagen demasiado grande para la notificación"))
            image = ImageOps.exif_transpose(source).convert("RGB")
        image.thumbnail((1280, 1280))
        found = [d for d in detections if d["image"] == index]
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default(size=14)
        for detection in found:
            box = detection.get("box")
            if not box or len(box) != 4:
                continue
            x1, y1, x2, y2 = [
                int(max(0, min(1, float(c))) * bound)
                for c, bound in zip(box, (image.width, image.height) * 2)
            ]
            if x2 <= x1 or y2 <= y1:
                continue
            draw.rectangle((x1, y1, x2, y2), outline="#69dfb8", width=2)
            label = detection_text(detection).replace(" — ", " - ")
            position = (x1, max(0, y1 - 19))
            bounds = draw.textbbox(position, label, font=font)
            draw.rectangle(bounds, fill="black")
            draw.text(position, label, font=font, fill="white")
        # sendPhoto limita la relación de aspecto a 20; añadir margen a panorámicas extremas.
        target = (
            max(image.width, math.ceil(image.height / 19)),
            max(image.height, math.ceil(image.width / 19)),
        )
        if image.size != target:
            image = ImageOps.pad(image, target)
        stream = io.BytesIO()
        image.save(stream, format="JPEG", quality=85)
        images.append(
            {
                "index": index,
                "filename": f"image-{index}.jpg",
                "content": stream.getvalue(),
                "detections": found,
            }
        )
    return images


def set_email_content(message, job, original, result, mailbox, images):
    detections = matching_detections(result, mailbox)
    text = alert_text(job, original, detections, inverse=mailbox.invert_detection)
    if result.get("skipped"):
        text += tr("\n\nImágenes omitidas: ") + "; ".join(result["skipped"])
    text += tr("\n\nLas imágenes analizadas se incluyen en el aviso; el correo original se adjunta completo.\n")
    message.set_content(text)
    html = "<html><body><h2>PiVigia</h2><p>" + escape(text).replace("\n", "<br>") + "</p>"
    for asset in images:
        title = escape(tr("Imagen {index}", index=asset["index"]))
        alt = escape(tr("Imagen analizada {index}", index=asset["index"]))
        html += (
            f"<h3>{title}</h3>"
            f'<img src="cid:pivigia-{asset["index"]}" alt="{alt}" '
            'style="max-width:100%;height:auto">'
        )
    message.add_alternative(html + "</body></html>", subtype="html")
    html_part = message.get_payload()[-1]
    for asset in images:
        html_part.add_related(
            asset["content"],
            maintype="image",
            subtype="jpeg",
            cid=f"<pivigia-{asset['index']}>",
            filename=asset["filename"],
            disposition="inline",
        )
    message.add_attachment(original)
