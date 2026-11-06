"""Private repository catalog metadata and safe, offline Markdown presentation."""

import posixpath
import re
from pathlib import Path, PurePosixPath
from urllib.parse import quote, unquote, urlencode, urlsplit

import yaml
from markdown_it import MarkdownIt

from .errors import Problem

MAX_DOCUMENT = 256 * 1024
MAX_IMAGE = 8 * 1024 * 1024
README_NAMES = ("README.md", "README.MD", "readme.md", "README.markdown", "README")
DOC_NAMES = ("DOCS.md", "docs.md", "DOCUMENTATION.md")
IMAGE_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


class RepositoryDocs:
    def __init__(self, root, repo_id=""):
        self.root = Path(root).absolute()
        self.repo_id = repo_id

    def safe_path(self, relative):
        path = PurePosixPath(relative)
        if (
            not relative
            or path.is_absolute()
            or any(
                part.startswith(".") and part not in {".github", ".forgejo"} for part in path.parts
            )
            or any(ord(char) < 32 for char in relative)
        ):
            raise Problem("La ruta de documentación no es segura.", "documentation_unsafe")
        current = self.root
        for part in path.parts:
            current = current / part
            if current.is_symlink():
                raise Problem(
                    "La documentación no puede usar enlaces simbólicos.", "documentation_unsafe"
                )
        if not current.resolve().is_relative_to(self.root.resolve()):
            raise Problem(
                "La documentación debe permanecer dentro del repositorio.", "documentation_unsafe"
            )
        return current

    def find(self, folder, names):
        for name in names:
            relative = (PurePosixPath(folder) / name).as_posix()
            try:
                path = self.safe_path(relative)
                if path.is_file() and path.stat().st_size <= MAX_DOCUMENT:
                    return relative
            except Problem:
                continue
        return None

    def text(self, relative, limit=MAX_DOCUMENT):
        path = self.safe_path(relative)
        if not path.is_file() or path.stat().st_size > limit:
            raise Problem(
                "El documento no existe o supera el tamaño permitido.", "documentation_missing"
            )
        try:
            with path.open("rb") as stream:
                content = stream.read(limit + 1)
            if len(content) > limit or b"\0" in content:
                raise ValueError("Invalid document")
            return content.decode("utf-8-sig")
        except (ValueError, OSError) as exc:
            raise Problem(
                "No se pudo leer el documento como texto UTF-8.", "documentation_unreadable"
            ) from exc

    def image(self, relative, *, content=True):
        path = self.safe_path(relative)
        media_type = IMAGE_TYPES.get(path.suffix.lower())
        if not media_type or not path.is_file() or path.stat().st_size > MAX_IMAGE:
            raise Problem(
                "Solo se admiten imágenes PNG, JPEG, GIF o WebP del repositorio.",
                "documentation_image",
            )
        with path.open("rb") as stream:
            data = stream.read(MAX_IMAGE + 1 if content else 16)
        valid = (
            media_type == "image/png"
            and data.startswith(b"\x89PNG\r\n\x1a\n")
            or media_type == "image/jpeg"
            and data.startswith(b"\xff\xd8\xff")
            or media_type == "image/gif"
            and data.startswith((b"GIF87a", b"GIF89a"))
            or media_type == "image/webp"
            and data.startswith(b"RIFF")
            and data[8:12] == b"WEBP"
        )
        if not valid or len(data) > MAX_IMAGE:
            raise Problem("La imagen del repositorio no es válida.", "documentation_image")
        return data, media_type

    def icon(self, folder):
        for name in ("icon.png", "logo.png"):
            relative = (PurePosixPath(folder) / name).as_posix()
            try:
                self.image(relative, content=False)
                return relative
            except (Problem, OSError):
                continue
        return None

    def app_files(self, folder):
        return {
            "readme_path": self.find(folder, README_NAMES),
            "docs_path": self.find(folder, DOC_NAMES),
            "icon_path": self.icon(folder),
        }

    def catalog(self, apps):
        metadata, manifest = {}, None
        for name in ("repository.yaml", "repository.yml", "repository.json"):
            candidate = self.root / name
            if candidate.exists() or candidate.is_symlink():
                try:
                    metadata = yaml.safe_load(self.text(name, 64 * 1024))
                except yaml.YAMLError as exc:
                    raise Problem(
                        "El archivo repository.yaml no es válido.", "catalog_invalid"
                    ) from exc
                if not isinstance(metadata, dict) or any(
                    key in metadata and not isinstance(metadata[key], str)
                    for key in ("name", "maintainer", "url", "description")
                ):
                    raise Problem("Los datos del catálogo no son válidos.", "catalog_invalid")
                manifest = name
                break
        readme = self.find(".", README_NAMES)
        summary = ""
        if readme:
            tokens = MarkdownIt("js-default", {"linkify": False}).parse(self.text(readme))
            for index, token in enumerate(tokens[:-1]):
                if token.type == "paragraph_open" and tokens[index + 1].type == "inline":
                    summary = " ".join(
                        child.content
                        for child in tokens[index + 1].children or []
                        if child.type in {"text", "code_inline"}
                    )
                    summary = " ".join(summary.split())[:240]
                    if summary:
                        break
        return {
            "kind": "collection"
            if manifest or len(apps) > 1
            else "single"
            if apps
            else "repository",
            "manifest": manifest,
            "name": metadata.get("name", "")[:200],
            "maintainer": metadata.get("maintainer", "")[:300],
            "description": metadata.get("description", "")[:500] or summary,
            "readme_path": readme,
            "icon_path": self.icon("."),
            "app_count": len(apps),
        }

    def local_reference(self, document, href):
        parsed = urlsplit(href)
        if parsed.scheme or parsed.netloc or not parsed.path:
            return None
        decoded = unquote(parsed.path)
        relative = (
            posixpath.normpath(posixpath.join(posixpath.dirname(document), decoded))
            if not decoded.startswith("/")
            else posixpath.normpath(decoded.lstrip("/"))
        )
        self.safe_path(relative)
        return relative

    def api_url(self, resource, relative):
        return (
            f"api/repos/{quote(self.repo_id, safe='')}/{resource}?{urlencode({'path': relative})}"
        )

    def document(self, relative):
        if (
            PurePosixPath(relative).suffix.lower() not in {".md", ".markdown"}
            and PurePosixPath(relative).name.upper() != "README"
        ):
            raise Problem("Solo se pueden consultar documentos Markdown.", "documentation_unsafe")
        markdown = self.text(relative)
        parser = MarkdownIt("js-default", {"linkify": False})
        tokens = parser.parse(markdown)
        headings = {}
        for index, token in enumerate(tokens[:-1]):
            if token.type == "heading_open":
                slug = (
                    re.sub(r"[^\w-]", "", tokens[index + 1].content.lower().replace(" ", "-"))
                    or "section"
                )
                counter = headings.get(slug, 0)
                headings[slug] = counter + 1
                token.attrSet("id", "pgm-readme-" + slug + (f"-{counter}" if counter else ""))
        for token in tokens:
            for child in token.children or []:
                if child.type == "image":
                    try:
                        target = self.local_reference(relative, child.attrGet("src") or "")
                        if not target:
                            raise Problem("External image")
                        self.image(target, content=False)
                        child.attrSet("src", self.api_url("asset", target))
                        child.attrSet("loading", "lazy")
                        child.attrSet("decoding", "async")
                    except (Problem, ValueError, OSError):
                        child.type, child.content, child.children = (
                            "text",
                            f"[{child.content or 'image'}]",
                            None,
                        )
                elif child.type == "link_open":
                    href = child.attrGet("href") or ""
                    try:
                        parsed = urlsplit(href)
                        if href.startswith("#"):
                            child.attrSet("href", "#pgm-readme-" + unquote(href[1:]))
                        elif (
                            parsed.scheme in {"http", "https", "mailto"}
                            and not parsed.username
                            and not parsed.password
                        ):
                            child.attrSet("target", "_blank")
                            child.attrSet("rel", "noopener noreferrer")
                        else:
                            target = self.local_reference(relative, href)
                            if not target or (
                                PurePosixPath(target).suffix.lower() not in {".md", ".markdown"}
                                and PurePosixPath(target).name.upper() != "README"
                            ):
                                raise Problem("Unsupported link")
                            self.text(target)
                            child.attrSet("href", self.api_url("document", target))
                    except (Problem, ValueError, OSError):
                        child.attrSet("href", "#")
        return {
            "available": True,
            "path": relative,
            "markdown": markdown,
            "html": parser.renderer.render(tokens, parser.options, {}),
        }
