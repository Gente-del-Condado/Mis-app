"""Install the bundled integration into the Home Assistant configuration."""

import json
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory

DOMAIN = "jacksignal"


def integration_version(directory: Path) -> str:
    """Validate that a directory contains a JackSignal integration."""
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    version = manifest.get("version")
    if manifest.get("domain") != DOMAIN or not isinstance(version, str) or not version:
        raise ValueError(f"Manifiesto de JackSignal no válido en {directory}")
    return version


def install(source: Path, config: Path) -> None:
    """Stage a complete update and preserve the previous integration."""
    version = integration_version(source)
    if not config.is_dir() or not (config / "configuration.yaml").is_file():
        raise ValueError(f"No se ha encontrado la configuración de Home Assistant en {config}")

    components = config / "custom_components"
    destination = components / DOMAIN
    previous = config / ".jacksignal-previous"
    for path in (components, destination, previous):
        if path.is_symlink():
            raise ValueError(f"No se puede sustituir ni seguir el enlace simbólico: {path}")

    components.mkdir(exist_ok=True)
    if previous.exists():
        integration_version(previous)
        # Recover the previous version if installation was interrupted between renames.
        if not destination.exists():
            previous.rename(destination)

    if destination.exists():
        installed = integration_version(destination)
        if installed == version:
            print(f"JackSignal {version} ya está instalado.")
            return

    with TemporaryDirectory(prefix=".jacksignal-stage-", dir=config) as temp:
        staged = Path(temp) / DOMAIN
        shutil.copytree(source, staged, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

        if destination.exists():
            if previous.exists():
                shutil.rmtree(previous)
            destination.rename(previous)
        try:
            staged.rename(destination)
        except OSError:
            if previous.exists():
                previous.rename(destination)
            raise

    print(f"Instalado JackSignal {version}. Reinicia Home Assistant para cargarlo.")


if __name__ == "__main__":
    try:
        install(Path(__file__).with_name(DOMAIN), Path("/homeassistant"))
    except (OSError, ValueError) as err:
        print(f"Ha fallado la instalación de JackSignal: {err}", file=sys.stderr)
        sys.exit(1)
