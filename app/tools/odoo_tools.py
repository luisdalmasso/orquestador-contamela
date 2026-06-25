from __future__ import annotations

from app.config.models import AppConfig
from app.services import mercadopago_service, odoo_catalog_service, odoo_client_service, odoo_invoice_service, odoo_media_service, odoo_pdf_service, odoo_restaurant_service, odoo_sales_service


def odoo_test_connection(config: AppConfig, arguments: dict) -> dict:
    return odoo_catalog_service.odoo_test_connection(config, arguments)


def odoo_list_products(config: AppConfig, arguments: dict) -> dict:
    return odoo_catalog_service.odoo_list_products(config, arguments)


def odoo_get_product_detail(config: AppConfig, arguments: dict) -> dict:
    return odoo_catalog_service.odoo_get_product_detail(config, arguments)


def odoo_get_ai_context(config: AppConfig, arguments: dict) -> dict:
    return odoo_catalog_service.odoo_get_ai_context(config, arguments)


def odoo_search_clients(config: AppConfig, arguments: dict) -> dict:
    return odoo_client_service.odoo_search_clients(config, arguments)


def odoo_list_clients(config: AppConfig, arguments: dict) -> dict:
    return odoo_client_service.odoo_list_clients(config, arguments)


def odoo_create_client(config: AppConfig, arguments: dict) -> dict:
    return odoo_client_service.odoo_create_client(config, arguments)


def odoo_create_order(config: AppConfig, arguments: dict) -> dict:
    return odoo_sales_service.odoo_create_order(config, arguments)


def odoo_create_cart(config: AppConfig, arguments: dict) -> dict:
    return odoo_sales_service.odoo_create_cart(config, arguments)


def odoo_add_item_to_cart(config: AppConfig, arguments: dict) -> dict:
    return odoo_sales_service.odoo_add_item_to_cart(config, arguments)


def odoo_get_cart_summary(config: AppConfig, arguments: dict) -> dict:
    return odoo_sales_service.odoo_get_cart_summary(config, arguments)


def odoo_confirm_cart(config: AppConfig, arguments: dict) -> dict:
    return odoo_sales_service.odoo_confirm_cart(config, arguments)


def odoo_cancel_cart(config: AppConfig, arguments: dict) -> dict:
    return odoo_sales_service.odoo_cancel_cart(config, arguments)


def odoo_create_invoice(config: AppConfig, arguments: dict) -> dict:
    return odoo_invoice_service.odoo_create_invoice(config, arguments)


def odoo_register_payment(config: AppConfig, arguments: dict) -> dict:
    return odoo_invoice_service.odoo_register_payment(config, arguments)


def odoo_upload_payment_proof(config: AppConfig, arguments: dict) -> dict:
    return odoo_media_service.odoo_upload_payment_proof(config, arguments)


def odoo_process_attachment_ocr(config: AppConfig, arguments: dict) -> dict:
    return odoo_media_service.odoo_process_attachment_ocr(config, arguments)


def odoo_process_pdf_document(config: AppConfig, arguments: dict) -> dict:
    return odoo_pdf_service.odoo_process_pdf_document(config, arguments)


def odoo_create_mercadopago_preference(config: AppConfig, arguments: dict) -> dict:
    return mercadopago_service.odoo_create_mercadopago_preference(config, arguments)


def odoo_get_restaurant_menu(config: AppConfig, arguments: dict) -> dict:
    return odoo_restaurant_service.odoo_get_restaurant_menu(config, arguments)


def odoo_get_invoice_status(config: AppConfig, arguments: dict) -> dict:
    return odoo_invoice_service.odoo_get_invoice_status(config, arguments)
