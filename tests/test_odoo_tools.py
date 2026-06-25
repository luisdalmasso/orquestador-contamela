import base64
from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.config.models import AppConfig
from app.main import app
from app.services import mercadopago_service, odoo_catalog_service, odoo_client_service, odoo_invoice_service, odoo_media_service, odoo_pdf_service, odoo_sales_service


client = TestClient(app)


class FakeOdooClient:
    def __init__(self) -> None:
        self.connection = type("Conn", (), {"name": "prod", "url": "http://odoo18:8069", "db": "demo"})()
        self.uid = 99

    def search_read(self, model, domain, fields, limit=None, offset=0, order=None):
        if model == "product.product" and limit == 1 and fields == ["id", "name"]:
            return [{"id": 1, "name": "Producto demo"}]
        if model == "product.template":
            return [
                {
                    "id": 10,
                    "name": "Yerba",
                    "default_code": "YB-1",
                    "list_price": 123.45,
                    "qty_available": 7,
                    "categ_id": [2, "Almacen"],
                    "description_sale": "Paquete 1kg",
                }
            ]
        if model == "res.partner":
            return [{"id": 5, "name": "Luis", "vat": "20123456789", "email": "luis@example.com", "phone": "123"}]
        if model == "sale.order":
            return [
                {
                    "id": 77,
                    "name": "S00077",
                    "partner_id": [5, "Luis"],
                    "state": "sale",
                    "invoice_status": "invoiced",
                    "amount_total": 2500.0,
                }
            ]
        if model == "account.move":
            return [
                {
                    "id": 88,
                    "name": "FA 0001-00000088",
                    "amount_total": 2500.0,
                    "state": "posted",
                    "payment_state": "paid",
                    "amount_residual": 0.0,
                }
            ]
        raise AssertionError(f"Unexpected search_read call for model={model}")

    def search_count(self, model, domain):
        if model == "product.template":
            return 1
        raise AssertionError(f"Unexpected search_count call for model={model}")

    def read(self, model, ids, fields):
        if model == "res.partner":
            return [{"vat": "20123456789"}]
        raise AssertionError(f"Unexpected read call for model={model}")


class FakeOdooSalesClient:
    def __init__(self) -> None:
        self.next_order_id = 500
        self.next_line_id = 900
        self.next_client_id = 700
        self.orders = {
            500: {
                "id": 500,
                "name": "S00500",
                "partner_id": [93, "Cliente Demo"],
                "order_line": [],
                "amount_total": 0.0,
                "state": "draft",
                "amount_untaxed": 0.0,
                "amount_tax": 0.0,
            }
        }
        self.lines = {}

    def create(self, model, data, **kwargs):
        if model == "res.partner":
            self.next_client_id += 1
            return self.next_client_id
        if model == "sale.order":
            self.next_order_id += 1
            self.orders[self.next_order_id] = {
                "id": self.next_order_id,
                "name": f"S{self.next_order_id:05d}",
                "partner_id": [data["partner_id"], "Cliente Demo"],
                "order_line": [],
                "amount_total": 0.0,
                "state": "draft",
                "amount_untaxed": 0.0,
                "amount_tax": 0.0,
            }
            return self.next_order_id
        if model == "sale.order.line":
            self.next_line_id += 1
            qty = float(data["product_uom_qty"])
            self.lines[self.next_line_id] = {
                "id": self.next_line_id,
                "order_id": data["order_id"],
                "product_id": [data["product_id"], "Producto demo"],
                "name": "Producto demo",
                "product_uom_qty": qty,
                "price_subtotal": qty * 100.0,
            }
            self.orders[data["order_id"]]["order_line"].append(self.next_line_id)
            self.orders[data["order_id"]]["amount_total"] = qty * 100.0
            self.orders[data["order_id"]]["amount_untaxed"] = qty * 100.0
            self.orders[data["order_id"]]["amount_tax"] = 0.0
            return self.next_line_id
        raise AssertionError(f"Unexpected create call for model={model}")

    def search_read(self, model, domain, fields, limit=None, offset=0, order=None):
        if model == "res.partner":
            if domain == [("vat", "=", "25123456")] or domain == [("vat", "=", "20999111222")]:
                return [{"id": 93, "name": "Cliente Demo", "vat": "25123456", "email": "demo@acme.com", "phone": "123"}]
            return []
        if model == "product.product":
            if domain == [("id", "=", 2)]:
                return [{"id": 2, "qty_available": 100.0, "uom_id": [1, "Units"]}]
            return []
        if model == "sale.order.line":
            order_id = next(item[2] for item in domain if item[0] == "order_id")
            product_id = next(item[2] for item in domain if item[0] == "product_id")
            for line in self.lines.values():
                if line["order_id"] == order_id and line["product_id"][0] == product_id:
                    return [{"id": line["id"], "product_uom_qty": line["product_uom_qty"]}]
            return []
        if model == "sale.order":
            order_id = next(item[2] for item in domain if item[0] == "id")
            order_data = self.orders.get(order_id)
            return [{"id": order_data["id"], "state": order_data["state"]}] if order_data else []
        raise AssertionError(f"Unexpected search_read call for model={model}")

    def read(self, model, ids, fields):
        if model == "sale.order":
            order = self.orders[ids[0]]
            return [{field: order.get(field) for field in fields}]
        if model == "res.partner":
            return [{"vat": "25123456"}]
        if model == "sale.order.line":
            return [
                {field: self.lines[line_id].get(field) for field in fields}
                for line_id in ids
            ]
        raise AssertionError(f"Unexpected read call for model={model}")

    def write(self, model, ids, data):
        if model != "sale.order.line":
            raise AssertionError(f"Unexpected write call for model={model}")
        line = self.lines[ids[0]]
        line["product_uom_qty"] = float(data["product_uom_qty"])
        line["price_subtotal"] = float(data["product_uom_qty"]) * 100.0
        order = self.orders[line["order_id"]]
        order["amount_total"] = line["price_subtotal"]
        order["amount_untaxed"] = line["price_subtotal"]
        return True

    def execute_method(self, model, method, args, **kwargs):
        if model != "sale.order":
            raise AssertionError(f"Unexpected execute_method call for model={model}")
        order_id = args[0][0]
        if method == "action_confirm":
            self.orders[order_id]["state"] = "sale"
            return True
        if method == "action_cancel":
            self.orders[order_id]["state"] = "cancel"
            return True
        raise AssertionError(f"Unexpected method {method}")


class FakeOdooInvoiceClient:
    def __init__(self) -> None:
        self.orders = {
            77: {
                "id": 77,
                "name": "S00077",
                "partner_id": [5, "Luis"],
                "state": "sale",
                "invoice_status": "to invoice",
                "amount_total": 2500.0,
            },
            78: {
                "id": 78,
                "name": "S00078",
                "partner_id": [5, "Luis"],
                "state": "sale",
                "invoice_status": "invoiced",
                "amount_total": 2500.0,
            },
        }
        self.invoices = {
            88: {
                "id": 88,
                "name": "FA 0001-00000088",
                "amount_total": 2500.0,
                "state": "posted",
                "payment_state": "paid",
                "amount_residual": 0.0,
                "invoice_origin": "S00078",
                "move_type": "out_invoice",
                "l10n_latam_document_type_id": [1, "INVOICES A"],
            }
        }
        self.invoice_lines = {188: {"id": 188, "move_id": 89, "account_type": "asset_receivable", "display_type": False}}
        self.doc_type_id = 1
        self.journal = {"id": 6, "name": "Bank", "type": "bank"}
        self.messages = []
        self.next_invoice_id = 89
        self.next_wizard_id = 1000

    def search_read(self, model, domain, fields, limit=None, offset=0, order=None):
        if model == "sale.order":
            order_id = next(item[2] for item in domain if item[0] == "id")
            order_data = self.orders.get(order_id)
            return [{field: order_data.get(field) for field in fields}] if order_data else []
        if model == "account.move":
            invoice_origin = next(item[2] for item in domain if item[0] == "invoice_origin")
            state_filter = next((item[2] for item in domain if item[0] == "state"), None)
            invoices_source = [
                invoice
                for invoice in self.invoices.values()
                if invoice["invoice_origin"] == invoice_origin and invoice["move_type"] == "out_invoice"
            ]
            if state_filter:
                invoices_source = [invoice for invoice in invoices_source if invoice.get("state") == state_filter]
            invoices = [{field: invoice.get(field) for field in fields} for invoice in invoices_source]
            return invoices[: limit or None]
        if model == "l10n_latam.document.type":
            return [{"id": self.doc_type_id, "name": "INVOICES A"}]
        if model == "account.journal":
            return [{"id": self.journal["id"], "name": self.journal["name"]}]
        if model == "account.move.line":
            move_id = next(item[2] for item in domain if item[0] == "move_id")
            lines = [
                {field: line.get(field) for field in fields}
                for line in self.invoice_lines.values()
                if line["move_id"] == move_id
            ]
            return lines[: limit or None]
        raise AssertionError(f"Unexpected search_read call for model={model}")

    def read(self, model, ids, fields):
        if model == "res.partner":
            return [{"vat": "20123456789"}]
        if model == "account.move":
            invoice = self.invoices[ids[0]]
            return [{field: invoice.get(field) for field in fields}]
        raise AssertionError(f"Unexpected read call for model={model}")

    def create(self, model, data, **kwargs):
        self.next_wizard_id += 1
        if model == "sale.advance.payment.inv":
            return self.next_wizard_id
        if model == "account.payment.register":
            return self.next_wizard_id
        raise AssertionError(f"Unexpected create call for model={model}")

    def write(self, model, ids, data):
        if model != "account.move":
            raise AssertionError(f"Unexpected write call for model={model}")
        self.invoices[ids[0]].update(data)
        return True

    def execute_method(self, model, method, args, **kwargs):
        if model == "sale.advance.payment.inv" and method == "create_invoices":
            invoice_id = self.next_invoice_id
            self.invoices[invoice_id] = {
                "id": invoice_id,
                "name": False,
                "amount_total": 2500.0,
                "state": "draft",
                "payment_state": "not_paid",
                "amount_residual": 2500.0,
                "invoice_origin": "S00077",
                "move_type": "out_invoice",
                "l10n_latam_document_type_id": False,
            }
            return {"res_id": invoice_id}
        if model == "account.move" and method == "action_post":
            invoice = self.invoices[args[0][0]]
            invoice["state"] = "posted"
            invoice["name"] = "FA 0001-00000089"
            self.invoice_lines[188]["move_id"] = invoice["id"]
            return True
        if model == "account.payment.register" and method == "action_create_payments":
            invoice = self.invoices[89]
            invoice["payment_state"] = "paid"
            invoice["amount_residual"] = 0.0
            return True
        raise AssertionError(f"Unexpected execute_method call for model={model}, method={method}")

    def post_message(self, model, record_id, subject, body, partner_ids):
        self.messages.append(
            {"model": model, "record_id": record_id, "subject": subject, "body": body, "partner_ids": partner_ids}
        )
        return True


class FakeOdooMediaClient:
    def __init__(self, attachment_pdf_bytes: bytes | None = None) -> None:
        self.order = {
            "id": 99,
            "state": "sale",
            "name": "S00099",
            "partner_id": [93, "Cliente Demo"],
        }
        self.next_attachment_id = 500
        self.messages = []
        self.attachments = {}
        if attachment_pdf_bytes is not None:
            self.attachments[444] = {
                "datas": base64.b64encode(attachment_pdf_bytes).decode("ascii"),
                "name": "comprobante_existente.pdf",
                "mimetype": "application/pdf",
            }

    def search_read(self, model, domain, fields, limit=None, offset=0, order=None):
        if model == "sale.order":
            return [{field: self.order.get(field) for field in fields}]
        raise AssertionError(f"Unexpected search_read call for model={model}")

    def search_count(self, model, domain):
        if model != "ir.attachment":
            raise AssertionError(f"Unexpected search_count call for model={model}")
        return 0

    def read(self, model, ids, fields):
        if model == "res.partner":
            return [{"vat": "25123456"}]
        if model == "ir.attachment":
            attachment = self.attachments.get(ids[0])
            return [{field: attachment.get(field) for field in fields}] if attachment else []
        raise AssertionError(f"Unexpected read call for model={model}")

    def create_attachment(self, model, record_id, filename, file_content):
        self.next_attachment_id += 1
        self.attachments[self.next_attachment_id] = {
            "name": filename,
            "datas": base64.b64encode(file_content).decode("ascii"),
            "mimetype": "application/pdf" if filename.endswith(".pdf") else "text/plain",
        }
        return self.next_attachment_id

    def post_message(self, model, record_id, subject, body, partner_ids):
        self.messages.append(
            {"model": model, "record_id": record_id, "subject": subject, "body": body, "partner_ids": partner_ids}
        )
        return True


class FakeMercadoPagoOdooClient:
    def __init__(self) -> None:
        self.order = {
            "id": 99,
            "name": "S00099",
            "partner_id": [93, "Cliente Demo"],
            "amount_total": 96558.0,
            "state": "sale",
            "order_line": [48],
        }
        self.lines = {
            48: {
                "product_id": [2, "Producto demo"],
                "name": "Producto demo",
                "product_uom_qty": 1,
                "price_unit": 79800.0,
            }
        }
        self.writes = []
        self.messages = []

    def search_read(self, model, domain, fields, limit=None, offset=0, order=None):
        if model == "sale.order":
            return [{field: self.order.get(field) for field in fields}]
        raise AssertionError(f"Unexpected search_read call for model={model}")

    def read(self, model, ids, fields):
        if model == "res.partner":
            return [{"vat": "25123456", "name": "Cliente Demo", "email": "demo@acme.com"}]
        if model == "sale.order.line":
            return [{field: self.lines[ids[0]].get(field) for field in fields}]
        raise AssertionError(f"Unexpected read call for model={model}")

    def write(self, model, ids, data):
        self.writes.append({"model": model, "ids": ids, "data": data})
        return True

    def post_message(self, model, record_id, subject, body, partner_ids):
        self.messages.append(
            {"model": model, "record_id": record_id, "subject": subject, "body": body, "partner_ids": partner_ids}
        )
        return True


def _build_text_pdf_bytes(text: str) -> bytes:
    stream = f"BT\n/F1 12 Tf\n72 720 Td\n({text}) Tj\nET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    chunks = [b"%PDF-1.4\n"]
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(sum(len(chunk) for chunk in chunks))
        chunks.append(f"{index} 0 obj\n".encode("ascii") + obj + b"\nendobj\n")
    xref_offset = sum(len(chunk) for chunk in chunks)
    chunks.append(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    chunks.append(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        chunks.append(f"{offset:010d} 00000 n \n".encode("ascii"))
    chunks.append(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return b"".join(chunks)


def _build_image_pdf_bytes(text: str) -> bytes:
    image = Image.new("RGB", (180, 80), color="white")
    draw = ImageDraw.Draw(image)
    draw.text((10, 30), text, fill="black")
    buffer = BytesIO()
    image.save(buffer, format="PDF")
    return buffer.getvalue()


def test_mcp_tools_lists_odoo_catalog() -> None:
    response = client.get("/mcp/tools")
    assert response.status_code == 200
    names = {tool["name"] for tool in response.json()["tools"]}
    assert "odoo_test_connection" in names
    assert "odoo_list_products" in names
    assert "odoo_create_invoice" in names
    assert "odoo_register_payment" in names
    assert "odoo_upload_payment_proof" in names
    assert "odoo_process_attachment_ocr" in names
    assert "odoo_process_pdf_document" in names
    assert "odoo_create_mercadopago_preference" in names
    assert "odoo_get_invoice_status" in names


def test_odoo_test_connection_via_mcp(monkeypatch) -> None:
    monkeypatch.setattr(odoo_catalog_service, "get_odoo_client", lambda config, arguments: FakeOdooClient())
    response = client.post("/mcp/call", json={"tool": "odoo_test_connection", "arguments": {}})
    assert response.status_code == 200
    payload = response.json()["result"]
    assert payload["success"] is True
    assert payload["odoo_db"] == "demo"
    assert payload["products_found"] == 1


def test_odoo_list_products_normalizes_id_product(monkeypatch) -> None:
    monkeypatch.setattr(odoo_catalog_service, "get_odoo_client", lambda config, arguments: FakeOdooClient())
    response = client.post(
        "/mcp/call",
        json={"tool": "odoo_list_products", "arguments": {"search": "yerba", "limit": 20, "offset": 0}},
    )
    assert response.status_code == 200
    payload = response.json()["result"]
    assert payload["success"] is True
    assert payload["products"][0]["id_product"] == 10
    assert payload["pagination"]["has_more"] is False


def test_odoo_search_clients_maps_vat_to_cuit(monkeypatch) -> None:
    monkeypatch.setattr(odoo_client_service, "get_odoo_client", lambda config, arguments: FakeOdooClient())
    response = client.post(
        "/mcp/call",
        json={"tool": "odoo_search_clients", "arguments": {"cuit_dni": "20123456789"}},
    )
    assert response.status_code == 200
    payload = response.json()["result"]
    assert payload["found"] is True
    assert payload["clients"][0]["cuit_dni"] == "20123456789"


def test_odoo_get_invoice_status_via_mcp(monkeypatch) -> None:
    monkeypatch.setattr(odoo_invoice_service, "get_odoo_client", lambda config, arguments: FakeOdooClient())
    response = client.post(
        "/mcp/call",
        json={"tool": "odoo_get_invoice_status", "arguments": {"order_id": 77, "cuit_dni": "20123456789"}},
    )
    assert response.status_code == 200
    payload = response.json()["result"]
    assert payload["has_invoice"] is True
    assert payload["is_paid"] is True


def test_odoo_create_invoice_via_mcp(monkeypatch) -> None:
    fake = FakeOdooInvoiceClient()
    monkeypatch.setattr(odoo_invoice_service, "get_odoo_client", lambda config, arguments: fake)
    response = client.post(
        "/mcp/call",
        json={"tool": "odoo_create_invoice", "arguments": {"order_id": 77, "cuit_dni": "20123456789"}},
    )
    assert response.status_code == 200
    payload = response.json()["result"]
    assert payload["success"] is True
    assert payload["invoice_id"] == 89
    assert payload["invoice_state"] == "posted"


def test_odoo_register_payment_via_mcp(monkeypatch) -> None:
    fake = FakeOdooInvoiceClient()
    fake.invoices[89] = {
        "id": 89,
        "name": "FA 0001-00000089",
        "amount_total": 2500.0,
        "state": "posted",
        "payment_state": "not_paid",
        "amount_residual": 2500.0,
        "invoice_origin": "S00077",
        "move_type": "out_invoice",
        "l10n_latam_document_type_id": [1, "INVOICES A"],
    }
    fake.invoice_lines[188]["move_id"] = 89
    monkeypatch.setattr(odoo_invoice_service, "get_odoo_client", lambda config, arguments: fake)
    response = client.post(
        "/mcp/call",
        json={
            "tool": "odoo_register_payment",
            "arguments": {"order_id": 77, "payment_id": "MP-123", "amount": 2500.0, "payment_method": "bank"},
        },
    )
    assert response.status_code == 200
    payload = response.json()["result"]
    assert payload["success"] is True
    assert payload["payment_state"] == "paid"
    assert fake.messages[0]["record_id"] == 89


def test_odoo_upload_payment_proof_via_mcp(monkeypatch) -> None:
    pdf_bytes = _build_text_pdf_bytes("Comprobante de pago")
    fake = FakeOdooMediaClient()
    monkeypatch.setattr(odoo_media_service, "get_odoo_client", lambda config, arguments: fake)
    response = client.post(
        "/mcp/call",
        json={
            "tool": "odoo_upload_payment_proof",
            "arguments": {
                "order_id": 99,
                "cuit_dni": "25123456",
                "filename": "comprobante.pdf",
                "file_base64": base64.b64encode(pdf_bytes).decode("ascii"),
                "run_ocr": True,
            },
        },
    )
    assert response.status_code == 200
    payload = response.json()["result"]
    assert payload["success"] is True
    assert payload["attachment_id"] == 501
    assert payload["ocr"]["status"] == "completed"
    assert payload["ocr"]["method"] == "embedded_text"
    assert payload["ocr"]["ocr_attachment_id"] == 502


def test_odoo_process_attachment_ocr_via_mcp(monkeypatch) -> None:
    pdf_bytes = _build_text_pdf_bytes("Texto OCR adjunto")
    fake = FakeOdooMediaClient(attachment_pdf_bytes=pdf_bytes)
    monkeypatch.setattr(odoo_media_service, "get_odoo_client", lambda config, arguments: fake)
    response = client.post(
        "/mcp/call",
        json={"tool": "odoo_process_attachment_ocr", "arguments": {"attachment_id": 444, "order_id": 99}},
    )
    assert response.status_code == 200
    payload = response.json()["result"]
    assert payload["success"] is True
    assert payload["ocr"]["status"] == "completed"
    assert payload["ocr"]["ocr_attachment_id"] == 501


def test_odoo_process_pdf_document_text_via_mcp() -> None:
    pdf_bytes = _build_text_pdf_bytes("Documento PDF general")
    response = client.post(
        "/mcp/call",
        json={
            "tool": "odoo_process_pdf_document",
            "arguments": {
                "filename": "general.pdf",
                "file_base64": base64.b64encode(pdf_bytes).decode("ascii"),
                "include_images_data": False,
            },
        },
    )
    assert response.status_code == 200
    payload = response.json()["result"]
    assert payload["success"] is True
    assert "Documento PDF general" in payload["text_content"]
    assert payload["stats"]["page_count"] == 1
    assert payload["stats"]["total_images"] == 0


def test_odoo_process_pdf_document_images_via_mcp() -> None:
    pdf_bytes = _build_image_pdf_bytes("Imagen embebida")
    response = client.post(
        "/mcp/call",
        json={
            "tool": "odoo_process_pdf_document",
            "arguments": {
                "filename": "images.pdf",
                "file_base64": base64.b64encode(pdf_bytes).decode("ascii"),
                "max_images": 5,
            },
        },
    )
    assert response.status_code == 200
    payload = response.json()["result"]
    assert payload["success"] is True
    assert payload["stats"]["total_images"] >= 1
    assert payload["images"][0]["data"]
    assert payload["images"][0]["page"] == 1


def test_odoo_create_mercadopago_preference_via_mcp(monkeypatch) -> None:
    fake = FakeMercadoPagoOdooClient()
    monkeypatch.setattr(mercadopago_service, "get_odoo_client", lambda config, arguments: fake)
    monkeypatch.setattr(mercadopago_service, "_mercadopago_access_token", lambda config: "TEST-token")
    monkeypatch.setattr(mercadopago_service, "_mercadopago_is_sandbox", lambda config: True)
    monkeypatch.setattr(
        mercadopago_service,
        "_mercadopago_request",
        lambda config, method, path, access_token, json_payload=None: {
            "id": "pref-123",
            "init_point": "https://www.mercadopago.com.ar/checkout/v1/redirect?pref_id=pref-123",
            "sandbox_init_point": "https://sandbox.mercadopago.com.ar/checkout/v1/redirect?pref_id=pref-123",
        },
    )
    response = client.post(
        "/mcp/call",
        json={"tool": "odoo_create_mercadopago_preference", "arguments": {"order_id": 99, "cuit_dni": "25123456"}},
    )
    assert response.status_code == 200
    payload = response.json()["result"]
    assert payload["success"] is True
    assert payload["preference_id"] == "pref-123"
    assert fake.writes[0]["data"]["client_order_ref"] == "pref-123"


def test_mercadopago_webhook_route_registers_payment(monkeypatch) -> None:
    fake = FakeMercadoPagoOdooClient()
    monkeypatch.setattr(mercadopago_service, "get_odoo_client", lambda config, arguments=None: fake)
    monkeypatch.setattr(mercadopago_service, "_mercadopago_access_token", lambda config: "TEST-token")
    monkeypatch.setattr(
        mercadopago_service,
        "_mercadopago_request",
        lambda config, method, path, access_token, json_payload=None: {
            "external_reference": "99",
            "status": "approved",
            "transaction_amount": 96558.0,
            "payment_method_id": "visa",
        },
    )
    monkeypatch.setattr(
        odoo_invoice_service,
        "odoo_register_payment",
        lambda config, arguments: {"success": True, "invoice_id": 64, "payment_state": "paid"},
    )
    response = client.post("/odoo/mercadopago/webhook", json={"type": "payment", "data": {"id": "mp-123"}})
    assert response.status_code == 200
    payload = response.json()
    assert payload["processed"] is True
    assert payload["payment_registration"]["payment_state"] == "paid"
    assert fake.messages[0]["record_id"] == 99


def test_mercadopago_return_route() -> None:
    response = client.get("/odoo/mercadopago/success?external_reference=99&collection_id=abc")
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["order_id"] == "99"


def test_app_config_redacts_odoo_sensitive_fields() -> None:
    payload = AppConfig().redacted_dict()
    assert payload["odoo"]["connections"]["prod"]["password_env"] == "***REDACTED***"
    assert payload["odoo"]["connections"]["prod"]["default_password"] == "***REDACTED***"


def test_odoo_create_client_via_mcp(monkeypatch) -> None:
    fake = FakeOdooSalesClient()
    monkeypatch.setattr(odoo_client_service, "get_odoo_client", lambda config, arguments: fake)
    response = client.post(
        "/mcp/call",
        json={"tool": "odoo_create_client", "arguments": {"name": "Nuevo Cliente", "cuit_dni": "20999111222", "email": "nuevo@test.com"}},
    )
    assert response.status_code == 200
    payload = response.json()["result"]
    assert payload["success"] is True
    assert payload["client_id"] == 701


def test_odoo_create_order_via_mcp(monkeypatch) -> None:
    fake = FakeOdooSalesClient()
    monkeypatch.setattr(odoo_sales_service, "get_odoo_client", lambda config, arguments: fake)
    response = client.post("/mcp/call", json={"tool": "odoo_create_order", "arguments": {"client_id": 93}})
    assert response.status_code == 200
    assert response.json()["result"]["success"] is True


def test_odoo_cart_flow_via_mcp(monkeypatch) -> None:
    fake = FakeOdooSalesClient()
    monkeypatch.setattr(odoo_sales_service, "get_odoo_client", lambda config, arguments: fake)

    create_cart = client.post("/mcp/call", json={"tool": "odoo_create_cart", "arguments": {"cuit_dni": "25123456"}})
    assert create_cart.status_code == 200
    order_id = create_cart.json()["result"]["order_id"]

    add_item = client.post(
        "/mcp/call",
        json={"tool": "odoo_add_item_to_cart", "arguments": {"order_id": order_id, "product_id": 2, "quantity": 2}},
    )
    assert add_item.status_code == 200
    assert add_item.json()["result"]["action"] == "created"

    summary = client.post(
        "/mcp/call",
        json={"tool": "odoo_get_cart_summary", "arguments": {"order_id": order_id, "cuit_dni": "25123456"}},
    )
    assert summary.status_code == 200
    assert summary.json()["result"]["summary"]["state"] == "draft"
    assert len(summary.json()["result"]["summary"]["lines"]) == 1

    confirm = client.post("/mcp/call", json={"tool": "odoo_confirm_cart", "arguments": {"order_id": order_id}})
    assert confirm.status_code == 200
    assert confirm.json()["result"]["state"] == "sale"

    cancel = client.post("/mcp/call", json={"tool": "odoo_cancel_cart", "arguments": {"order_id": order_id}})
    assert cancel.status_code == 200
    assert cancel.json()["result"]["state"] == "cancel"
