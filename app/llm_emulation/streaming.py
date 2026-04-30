from __future__ import annotations

import json
from collections.abc import Iterator

from app.llm_emulation.nanobot_serve_bridge import NanobotServeError


def passthrough_stream(byte_iterator: Iterator[bytes]):
    try:
        for chunk in byte_iterator:
            yield chunk
    except NanobotServeError as exc:
        detail = exc.detail
        if not isinstance(detail, str):
            detail = json.dumps(detail, ensure_ascii=False)
        payload = {
            "error": {
                "message": detail,
                "type": "invalid_request_error" if exc.status_code < 500 else "server_error",
            }
        }
        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode()
        yield b"data: [DONE]\n\n"
