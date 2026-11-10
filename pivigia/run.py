"""Traduce opciones de Supervisor a variables; conserva puertos internos e identidad."""
import json
import os
from pathlib import Path

from pivigia.i18n import match_language, tr

options = json.loads(Path("/data/options.json").read_text())
language = options.get("language")
if language:
    if not match_language(language):
        raise SystemExit(tr("Idioma no disponible"))
    os.environ["PIVIGIA_LANGUAGE"] = match_language(language)
token = options.get("admin_token")
if not isinstance(token, str) or len(token) < 16:
    raise SystemExit(tr("Configura admin_token con al menos 16 caracteres en las opciones del complemento"))
os.environ["PIVIGIA_ADMIN_TOKEN"] = token
os.environ["PIVIGIA_DEPLOYMENT"] = "homeassistant"
login = options.get("panel_login", "both")
if login not in {"token", "homeassistant", "both"}:
    raise SystemExit(tr("Elige un método de acceso válido: both, homeassistant o token"))
os.environ["PIVIGIA_PANEL_LOGIN"] = login
# Supervisor maps the host ports. Keep the container ports stable for webui/watchdog.
os.environ["PIVIGIA_WEB_BIND"] = "0.0.0.0"
os.environ["PIVIGIA_WEB_PORT"] = "8099"
os.environ["PIVIGIA_SMTP_BIND"] = "0.0.0.0"
os.environ["PIVIGIA_SMTP_PORT"] = "2525"
os.environ["PIVIGIA_TRUSTED_NETWORKS"] = options.get("trusted_networks") or ""
os.environ["PIVIGIA_ALLOW_PLAIN_AUTH"] = "1" if options.get("allow_plain_auth") else "0"
for key in ("tls_cert", "tls_key"):
    os.environ["PIVIGIA_" + key.upper()] = options.get(key) or ""
os.execvp("python", ["python", "-m", "pivigia.web"])
