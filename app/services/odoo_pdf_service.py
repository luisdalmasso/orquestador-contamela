from __future__ import annotations

import base64
import logging
import os
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Any

from app.config.models import AppConfig
from app.utils.security import resolve_allowed_path

try:  # pragma: no cover - depende del runtime construido
    import fitz  # PyMuPDF
except ImportError:  # pragma: no cover
    fitz = None

try:  # pragma: no cover - depende del runtime construido
    from unstructured.partition.pdf import partition_pdf
except ImportError:  # pragma: no cover
    partition_pdf = None

try:  # pragma: no cover - depende del runtime construido
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    from PyPDF2 import PdfReader  # type: ignore


logger = logging.getLogger("conti.odoo.pdf")


def odoo_process_pdf_document(config: AppConfig, arguments: dict[str, Any]) -> dict[str, Any]:
    _ensure_pdf_runtime()

    filename, file_content = _load_pdf_bytes(config, arguments)
    include_images_data = bool(arguments.get("include_images_data", True))
    max_images_raw = arguments.get("max_images")
    max_images = int(max_images_raw) if max_images_raw is not None else None
    if max_images is not None and max_images < 1:
        raise ValueError("'max_images' debe ser >= 1")

    temp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix="odoo-pdf-", suffix=".pdf", delete=False) as tmp:
            tmp.write(file_content)
            temp_path = tmp.name

        file_size_mb = os.path.getsize(temp_path) / (1024 * 1024)
        page_count = len(PdfReader(BytesIO(file_content)).pages)
        logger.info("Processing PDF: %s (%.2fMB)", filename, file_size_mb)

        elements = partition_pdf(
            filename=temp_path,
            strategy="fast",
            infer_table_structure=True,
        )
        element_types = _count_element_types(elements)
        text_content = "\n\n".join(str(element) for element in elements)
        text_method = "unstructured.partition_pdf(strategy=fast)"
        if not text_content.strip():
            text_content = _extract_text_with_pypdf(file_content)
            if text_content.strip():
                text_method = "unstructured.partition_pdf(strategy=fast)+pypdf-fallback"

        images_data = _extract_images_with_pymupdf(
            temp_path=temp_path,
            include_images_data=include_images_data,
            max_images=max_images,
        )

        return {
            "success": True,
            "filename": filename,
            "text_content": text_content,
            "images": images_data["images"],
            "stats": {
                "page_count": page_count,
                "total_elements": len(elements),
                "total_images": images_data["total_images"],
                "returned_images": len(images_data["images"]),
                "images_truncated": images_data["images_truncated"],
                "element_types": element_types,
                "file_size_mb": round(file_size_mb, 2),
                "text_extraction_method": text_method,
                "image_extraction_method": "pymupdf",
            },
        }
    except Exception as exc:
        logger.error("Error processing PDF document: %s", exc, exc_info=True)
        raise RuntimeError(f"Processing error: {exc}") from exc
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError as cleanup_error:
                logger.warning("Could not remove temporary file %s: %s", temp_path, cleanup_error)


def _extract_images_with_pymupdf(temp_path: str, include_images_data: bool, max_images: int | None) -> dict[str, Any]:
    images: list[dict[str, Any]] = []
    total_images = 0
    images_truncated = False

    pdf_document = fitz.open(temp_path)
    try:
        for page_num in range(len(pdf_document)):
            page = pdf_document[page_num]
            image_list = page.get_images(full=True)
            page_text = page.get_text().strip() if image_list else ""

            for img_index, img in enumerate(image_list, start=1):
                total_images += 1
                if max_images is not None and len(images) >= max_images:
                    images_truncated = True
                    continue

                xref = img[0]
                base_image = pdf_document.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]
                image_entry = {
                    "filename": f"page_{page_num + 1}_image_{img_index}.{image_ext}",
                    "size": len(image_bytes),
                    "page": page_num + 1,
                    "format": image_ext,
                    "page_text": page_text,
                }
                if include_images_data:
                    image_entry["data"] = base64.b64encode(image_bytes).decode("utf-8")
                images.append(image_entry)
    finally:
        pdf_document.close()

    return {
        "images": images,
        "total_images": total_images,
        "images_truncated": images_truncated,
    }


def _count_element_types(elements: list[Any]) -> dict[str, int]:
    element_types: dict[str, int] = {}
    for element in elements:
        name = type(element).__name__
        element_types[name] = element_types.get(name, 0) + 1
    return element_types


def _extract_text_with_pypdf(file_content: bytes) -> str:
    reader = PdfReader(BytesIO(file_content))
    page_sections: list[str] = []
    for index, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            page_sections.append(f"=== PAGINA {index} ===\n{text}")
    return "\n\n".join(page_sections)


def _load_pdf_bytes(config: AppConfig, arguments: dict[str, Any]) -> tuple[str, bytes]:
    file_path = arguments.get("file_path")
    file_base64 = arguments.get("file_base64")
    if bool(file_path) == bool(file_base64):
        raise ValueError("Debe enviar exactamente uno de 'file_path' o 'file_base64'")

    if file_path:
        resolved = resolve_allowed_path(config, str(file_path))
        if not resolved.exists() or not resolved.is_file():
            raise ValueError(f"Archivo no encontrado: {file_path}")
        filename = str(arguments.get("filename") or resolved.name).strip()
        file_content = resolved.read_bytes()
    else:
        filename = _required_str(arguments, "filename")
        try:
            file_content = base64.b64decode(str(file_base64), validate=True)
        except Exception as exc:
            raise ValueError("'file_base64' no es base64 válido") from exc

    if not filename.lower().endswith(".pdf"):
        raise ValueError("Solo se permiten PDF.")
    if len(file_content) < 50:
        raise ValueError("Archivo PDF vacío o muy pequeño.")
    return Path(filename).name, file_content


def _ensure_pdf_runtime() -> None:
    missing: list[str] = []
    if partition_pdf is None:
        missing.append("unstructured")
    if fitz is None:
        missing.append("PyMuPDF")
    if missing:
        raise RuntimeError(f"Dependencias PDF no instaladas: {', '.join(missing)}")


def _required_str(arguments: dict[str, Any], key: str) -> str:
    value = str(arguments.get(key) or "").strip()
    if not value:
        raise ValueError(f"Se requiere '{key}'")
    return value


def odoo_convert_pdf_to_html(config: AppConfig, arguments: dict[str, Any]) -> dict[str, Any]:
    """Convierte un PDF a HTML con posicionamiento absoluto y extracción de imágenes."""
    tenant = str(arguments.get("tenant") or "resto").strip()
    url = arguments.get("url")
    file_path = arguments.get("file_path")
    file_base64 = arguments.get("file_base64")

    file_content = None
    filename = "document.pdf"

    if url:
        import requests
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        file_content = response.content
        filename = url.split("/")[-1].split("?")[0]
        if not filename.lower().endswith(".pdf"):
            filename = "document.pdf"
    elif file_path:
        resolved = resolve_allowed_path(config, str(file_path))
        if not resolved.exists() or not resolved.is_file():
            raise ValueError(f"Archivo no encontrado: {file_path}")
        file_content = resolved.read_bytes()
        filename = resolved.name
    elif file_base64:
        file_content = base64.b64decode(str(file_base64))
        filename = arguments.get("filename", "document.pdf")
    else:
        raise ValueError("Debe enviar al menos uno de 'url', 'file_path' o 'file_base64'")

    if not file_content or len(file_content) < 50:
        raise ValueError("Archivo PDF vacío o inválido.")

    import hashlib
    pdf_hash = hashlib.md5(file_content).hexdigest()

    # Sanitizar el nombre de archivo
    clean_filename = "".join(c for c in filename if c.isalnum() or c in ".-_").strip()
    if not clean_filename:
        clean_filename = "document.pdf"
    base_name, _ = os.path.splitext(clean_filename)

    html_filename = f"{base_name}-{pdf_hash}.html"
    dest_dir = f"/compose/documentos_listos/{tenant}"
    html_path = os.path.join(dest_dir, html_filename)
    img_dir = os.path.join(dest_dir, f"img_{pdf_hash}")
    relative_img_dir = f"img_{pdf_hash}"

    from app.utils.pdf_to_html import pdf_bytes_to_html
    pdf_bytes_to_html(
        pdf_bytes=file_content,
        output_html_path=html_path,
        output_img_dir=img_dir,
        relative_img_dir=relative_img_dir
    )

    django_path = f"/docs_chatui/{tenant}/{html_filename}"

    return {
        "success": True,
        "filename": filename,
        "html_filename": html_filename,
        "path": django_path,
        "url": django_path,
    }

