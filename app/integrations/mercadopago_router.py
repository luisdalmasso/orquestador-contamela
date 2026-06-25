from __future__ import annotations

from fastapi import APIRouter, Request

from app.config.loader import load_config
from app.services import mercadopago_service


router = APIRouter(prefix="/odoo/mercadopago", tags=["mercadopago"])


@router.post("/webhook")
async def post_webhook(request: Request) -> dict:
    payload = await request.json()
    query_params = dict(request.query_params)
    headers = dict(request.headers)
    return mercadopago_service.process_mercadopago_webhook(
        load_config(),
        payload=payload,
        headers=headers,
        query_params=query_params,
    )


@router.get("/webhook")
async def get_webhook(request: Request) -> dict:
    return mercadopago_service.process_mercadopago_webhook(
        load_config(),
        payload={},
        headers=dict(request.headers),
        query_params=dict(request.query_params),
    )


@router.get("/success")
async def get_success(request: Request) -> dict:
    return mercadopago_service.mercadopago_return_payload("success", dict(request.query_params))


@router.get("/failure")
async def get_failure(request: Request) -> dict:
    return mercadopago_service.mercadopago_return_payload("failure", dict(request.query_params))


@router.get("/pending")
async def get_pending(request: Request) -> dict:
    return mercadopago_service.mercadopago_return_payload("pending", dict(request.query_params))
