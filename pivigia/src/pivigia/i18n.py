"""Catálogos compartidos sin conexión: un locales/<código>.json por idioma.

Las claves españolas son identificadores estables, al estilo gettext. No traducir
claves de protocolo ni contenido del usuario. ContextVar aísla cada petición;
los trabajos automáticos usan el idioma del servicio salvo contexto explícito.
"""

import json
import os
import re
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path
from string import Formatter

DEFAULT_LANGUAGE = "es"
_language = ContextVar("pivigia_language", default=None)
_service_language = DEFAULT_LANGUAGE


def N_(message):
    """Marca un mensaje para extraerlo sin traducir durante la importación del módulo."""
    return message


@lru_cache
def catalogs():
    return {path.stem: json.loads(path.read_text(encoding="utf-8"))
            for path in sorted((Path(__file__).parent / "locales").glob("*.json"))}


def match_language(value):
    value = str(value or "").strip().lower().replace("_", "-")
    return next((code for code in (value, value.split("-")[0]) if code in catalogs()), None)


def service_language(saved=None):
    return match_language(os.environ.get("PIVIGIA_LANGUAGE")) or match_language(saved) or _service_language


def set_service_language(value):
    global _service_language
    _service_language = match_language(value) or DEFAULT_LANGUAGE


def current_language():
    return _language.get() or service_language()


def negotiate_language(header, fallback=None):
    choices = []
    for item in (header or "").split(","):
        parts = item.strip().split(";")
        try:
            quality = float(parts[1].strip().removeprefix("q=")) if len(parts) > 1 else 1
        except ValueError:
            continue
        code = match_language(parts[0])
        if code and 0 < quality <= 1:
            choices.append((quality, code))
    return max(choices, key=lambda item: item[0])[1] if choices else (fallback or service_language())


@contextmanager
def use_language(language):
    token = _language.set(match_language(language) or DEFAULT_LANGUAGE)
    try:
        yield
    finally:
        _language.reset(token)


def tr(message, *, language=None, **values):
    code = match_language(language) if language else current_language()
    translated = catalogs().get(code, {}).get("messages", {}).get(message) or message
    if not values:
        return translated
    try:
        return translated.format(**values)
    except (KeyError, ValueError, IndexError):
        return message.format(**values)


def language_info():
    return [{"code": code, **catalog["meta"]} for code, catalog in catalogs().items()]


def browser_catalogs():
    # Solo se incrustan mensajes del panel; los catálogos del servidor permanecen en Python.
    return {code: {"meta": catalog["meta"], "messages": {
        key: value for key, value in catalog["messages"].items() if key in catalogs()["es"]["ui"]}}
        for code, catalog in catalogs().items()}


def translate_saved(message):
    """Traduce campos propios del historial; conserva detalles externos y contenido del usuario."""
    for catalog in catalogs().values():
        for source, translated in catalog["messages"].items():
            if message == translated and not re.search(r"\{\w+", source):
                return tr(source)
    for pattern, source in saved_templates():
        match = pattern.fullmatch(message)
        if match:
            return tr(source, **match.groupdict())
    # Los nombres de excepciones son identificadores técnicos; traducir solo su mensaje.
    prefix, separator, detail = message.partition(": ")
    if separator and re.fullmatch(r"[A-Za-z]+(?:Error|Exception)", prefix):
        return prefix + separator + translate_saved(detail)
    return tr(message)


@lru_cache
def saved_templates():
    result = []
    for catalog in catalogs().values():
        for source, translated in catalog["messages"].items():
            parts = list(Formatter().parse(translated))
            if not any(name for _, name, _, _ in parts) or any(spec or conversion for _, _, spec, conversion in parts):
                continue
            pattern, names = "", set()
            for literal, name, _, _ in parts:
                pattern += re.escape(literal)
                if name:
                    pattern += f"(?P={name})" if name in names else f"(?P<{name}>.+?)"
                    names.add(name)
            result.append((re.compile(pattern), source))
    return result
