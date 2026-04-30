from __future__ import annotations

import logging
import uuid

from fastapi import Request


logger = logging.getLogger("conti-backend")


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    # DEBUG en los módulos del bridge LLM para trazar el flujo completo
    for _name in ("conti.llm_router", "conti.llm_service", "conti.llm_bridge"):
        logging.getLogger(_name).setLevel(logging.DEBUG)


async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request_id=%s method=%s path=%s status=%s",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
    )
    return response
