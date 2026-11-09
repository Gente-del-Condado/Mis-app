#!/usr/bin/env python3
"""Descarga reproducible; no importa OpenCV ni ejecuta código remoto."""

import hashlib
import os
import sys
from pathlib import Path
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pivigia.i18n import tr

COMMIT = "bb17b6c3eef36d80be441ae8e5339be66e8e3b7a"
FILES = {
    "deploy.prototxt": (
        "deploy.prototxt",
        "2d180f723b3109e21f8287f6b3c691390d07b60eed998327cd3259ffa0e50608",
    ),
    "mobilenet.caffemodel": (
        "mobilenet_iter_73000.caffemodel",
        "52eed8be80522c152a17fb56740de705b79881bde1a167e0e747310523685fc7",
    ),
}


def main():
    directory = Path(os.environ.get("PIVIGIA_MODELS", "models"))
    directory.mkdir(parents=True, exist_ok=True)
    for local, (remote, checksum) in FILES.items():
        target = directory / local
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == checksum:
            print(tr("{file}: verificado", file=local))
            continue
        url = f"https://raw.githubusercontent.com/chuanqi305/MobileNet-SSD/{COMMIT}/{remote}"
        with urlopen(url, timeout=120) as response:
            content = response.read(30_000_001)
        if len(content) > 30_000_000 or hashlib.sha256(content).hexdigest() != checksum:
            raise RuntimeError(tr("Integridad incorrecta: {file}", file=local))
        temporary = target.with_suffix(".tmp")
        temporary.write_bytes(content)
        temporary.replace(target)
        print(tr("{file}: descargado y verificado", file=local))


if __name__ == "__main__":
    main()
