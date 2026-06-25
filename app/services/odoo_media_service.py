from __future__ import annotations

import base64
import io
import logging
from pathlib import Path
from typing import Any

import numpy as np
from pdf2image import convert_from_bytes
from PyPDF2 import PdfReader

from app.config.models import AppConfig
from app.services.odoo_rpc import get_odoo_client
from app.utils.security import resolve_allowed_path

try:
    from paddleocr import PaddleOCR
except ImportError:  # pragma: no cover - depende del runtime
    PaddleOCR = None

try:
    import easyocr
except ImportError:  # pragma: no cover - depende del runtime
    easyocr = None


logger = logging.getLogger("conti.odoo.media")


def odoo_upload_payment_proof(config: AppConfig, arguments: dict[str, Any]) -> dict[str, Any]:
    order_id = _required_int(arguments, "order_id")
    cuit_dni = _required_str(arguments, "cuit_dni")
    run_ocr = bool(arguments.get("run_ocr", False))

    filename, file_content = _load_pdf_bytes(config, arguments)
    client = get_odoo_client(config, arguments)
    order = _validate_payment_proof_order(client, order_id, cuit_dni)

    comprobante_filename = f"comprobante_{order['name']}_{filename}"
    attachment_id = client.create_attachment(
        model="sale.order",
        record_id=order_id,
        filename=comprobante_filename,
        file_content=file_content,
    )
    client.post_message(
        model="sale.order",
        record_id=order_id,
        subject=f"Comprobante para {order['name']}",
        body=(
            f"Comprobante recibido para {order['name']}\n\n"
            f"Archivo: {filename}\n"
            f"Cliente: {order['partner_name']}\n\n"
            "Pendiente de verificación."
        ),
        partner_ids=[],
    )

    response: dict[str, Any] = {
        "success": True,
        "message": "Comprobante recibido.",
        "order_id": order_id,
        "order_name": order["name"],
        "attachment_id": attachment_id,
        "attachment_name": comprobante_filename,
        "file_size_bytes": len(file_content),
    }
    if run_ocr:
        response["ocr"] = _process_pdf_ocr(
            config=config,
            client=client,
            order_id=order_id,
            attachment_id=attachment_id,
            filename=filename,
            file_content=file_content,
        )
    else:
        response["ocr"] = {"requested": False, "status": "skipped", "message": "OCR no solicitado."}
    return response


def odoo_process_attachment_ocr(config: AppConfig, arguments: dict[str, Any]) -> dict[str, Any]:
    attachment_id = _required_int(arguments, "attachment_id")
    order_id = _required_int(arguments, "order_id")

    client = get_odoo_client(config, arguments)
    attachments = client.read("ir.attachment", [attachment_id], ["datas", "name", "mimetype"])
    if not attachments:
        raise ValueError(f"Adjunto no encontrado: {attachment_id}")

    attachment = attachments[0]
    encoded = attachment.get("datas")
    if not encoded:
        raise ValueError(f"Adjunto vacío: {attachment_id}")

    filename = str(attachment.get("name") or f"attachment_{attachment_id}.pdf")
    if not filename.lower().endswith(".pdf"):
        raise ValueError("Solo se procesan comprobantes PDF.")

    file_content = base64.b64decode(encoded)
    return {
        "success": True,
        "attachment_id": attachment_id,
        "order_id": order_id,
        "ocr": _process_pdf_ocr(
            config=config,
            client=client,
            order_id=order_id,
            attachment_id=attachment_id,
            filename=filename,
            file_content=file_content,
        ),
    }


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
    max_bytes = config.odoo.payment_proof_max_mb * 1024 * 1024
    if len(file_content) > max_bytes:
        raise ValueError(f"Archivo no puede exceder {config.odoo.payment_proof_max_mb}MB.")
    if len(file_content) < 100:
        raise ValueError("Archivo PDF vacío o muy pequeño.")

    _validate_pdf(file_content)
    return Path(filename).name, file_content


def _validate_pdf(file_content: bytes) -> None:
    try:
        reader = PdfReader(io.BytesIO(file_content))
        if len(reader.pages) < 1:
            raise ValueError("PDF sin páginas.")
    except Exception as exc:
        raise ValueError("El archivo no es un PDF válido.") from exc


def _validate_payment_proof_order(client: Any, order_id: int, cuit_dni: str) -> dict[str, Any]:
    orders = client.search_read("sale.order", [("id", "=", order_id)], ["id", "state", "name", "partner_id"], limit=1)
    if not orders:
        raise ValueError(f"Pedido ID {order_id} no encontrado.")
    order = orders[0]

    existing_attachments = client.search_count(
        "ir.attachment",
        [("res_model", "=", "sale.order"), ("res_id", "=", order_id), ("name", "ilike", "comprobante")],
    )
    if existing_attachments > 0:
        raise ValueError("Ya existe un comprobante.")
    if order["state"] != "sale":
        raise ValueError("Pedido no está en estado 'Orden de Venta'.")

    partner_id = order.get("partner_id", [None])[0]
    partners = client.read("res.partner", [partner_id], ["vat"]) if partner_id else []
    if not partners or partners[0].get("vat") != cuit_dni:
        raise ValueError("CUIT/DNI no coincide.")

    order["partner_name"] = order.get("partner_id", [None, "N/A"])[1]
    return order


def _process_pdf_ocr(
    config: AppConfig,
    client: Any,
    order_id: int,
    attachment_id: int,
    filename: str,
    file_content: bytes,
) -> dict[str, Any]:
    if not config.odoo.ocr_enabled:
        return {
            "requested": True,
            "status": "disabled",
            "message": "OCR deshabilitado por configuración.",
        }

    extraction = _extract_text(file_content)
    result = {
        "requested": True,
        "status": extraction["status"],
        "method": extraction["method"],
        "message": extraction["message"],
        "page_count": extraction.get("page_count"),
        "text_line_count": extraction.get("text_line_count"),
        "source_attachment_id": attachment_id,
    }
    extracted_text = extraction.get("text")
    if not extracted_text:
        return result

    ocr_filename = f"ocr_{Path(filename).stem}.txt"
    new_attachment_id = client.create_attachment(
        model="sale.order",
        record_id=order_id,
        filename=ocr_filename,
        file_content=extracted_text.encode("utf-8"),
    )
    client.post_message(
        model="sale.order",
        record_id=order_id,
        subject="OCR Completado",
        body=(
            f"Procesamiento OCR/texto completado para {filename}\n\n"
            f"Resultado adjunto: {ocr_filename}\n"
            f"Método: {extraction['method']}\n"
            f"Páginas procesadas: {extraction.get('page_count', 0)}"
        ),
        partner_ids=[],
    )
    result["ocr_attachment_id"] = new_attachment_id
    return result


def _extract_text(file_content: bytes) -> dict[str, Any]:
    embedded = _extract_embedded_pdf_text(file_content)
    if embedded.get("text"):
        return {
            "status": "completed",
            "method": "embedded_text",
            "message": "Texto embebido extraído del PDF.",
            **embedded,
        }

    if PaddleOCR and convert_from_bytes:
        return _extract_with_paddleocr(file_content)
    if easyocr and convert_from_bytes:
        return _extract_with_easyocr(file_content)

    return {
        "status": "unavailable",
        "method": "none",
        "message": "OCR no disponible - faltan dependencias y el PDF no contiene texto embebido.",
        "page_count": embedded.get("page_count", 0),
        "text_line_count": 0,
    }


def _extract_embedded_pdf_text(file_content: bytes) -> dict[str, Any]:
    reader = PdfReader(io.BytesIO(file_content))
    page_count = len(reader.pages)
    page_sections: list[str] = []
    text_lines = 0
    for index, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if not text:
            continue
        page_sections.append(f"=== PAGINA {index} ===\n{text}")
        text_lines += len([line for line in text.splitlines() if line.strip()])
    return {
        "text": "\n\n".join(page_sections),
        "page_count": page_count,
        "text_line_count": text_lines,
    }


def _extract_with_paddleocr(file_content: bytes) -> dict[str, Any]:
    images = convert_from_bytes(file_content)
    ocr = PaddleOCR(use_textline_orientation=True, lang="es")
    page_sections: list[str] = []
    text_lines = 0
    for index, image in enumerate(images, start=1):
        page_texts: list[str] = []
        result = ocr.predict(np.array(image))
        if result and isinstance(result, list) and len(result) > 0:
            ocr_result = result[0]
            rec_texts = getattr(ocr_result, "rec_texts", None)
            if rec_texts is None and isinstance(ocr_result, dict):
                rec_texts = ocr_result.get("rec_texts")
            for text in rec_texts or []:
                cleaned = str(text).strip()
                if cleaned:
                    page_texts.append(cleaned)
        if page_texts:
            page_sections.append(f"=== PAGINA {index} ===\n" + "\n".join(page_texts))
            text_lines += len(page_texts)
    if not page_sections:
        return {
            "status": "completed",
            "method": "paddleocr",
            "message": "OCR ejecutado pero no detectó texto.",
            "page_count": len(images),
            "text_line_count": 0,
        }
    return {
        "status": "completed",
        "method": "paddleocr",
        "message": "OCR ejecutado con PaddleOCR.",
        "text": "\n\n".join(page_sections),
        "page_count": len(images),
        "text_line_count": text_lines,
    }


def _extract_with_easyocr(file_content: bytes) -> dict[str, Any]:
    images = convert_from_bytes(file_content)
    reader = easyocr.Reader(["es", "en"])
    page_sections: list[str] = []
    text_lines = 0
    for index, image in enumerate(images, start=1):
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        result = reader.readtext(buffer.getvalue(), detail=0, paragraph=True)
        page_texts = [str(text).strip() for text in result if str(text).strip()]
        if page_texts:
            page_sections.append(f"=== PAGINA {index} ===\n" + "\n".join(page_texts))
            text_lines += len(page_texts)
    if not page_sections:
        return {
            "status": "completed",
            "method": "easyocr",
            "message": "OCR ejecutado pero no detectó texto.",
            "page_count": len(images),
            "text_line_count": 0,
        }
    return {
        "status": "completed",
        "method": "easyocr",
        "message": "OCR ejecutado con EasyOCR.",
        "text": "\n\n".join(page_sections),
        "page_count": len(images),
        "text_line_count": text_lines,
    }


def _required_int(arguments: dict[str, Any], key: str) -> int:
    value = arguments.get(key)
    if value is None or str(value).strip() == "":
        raise ValueError(f"Se requiere '{key}'")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"'{key}' debe ser entero") from exc


def _required_str(arguments: dict[str, Any], key: str) -> str:
    value = str(arguments.get(key) or "").strip()
    if not value:
        raise ValueError(f"Se requiere '{key}'")
    return value
