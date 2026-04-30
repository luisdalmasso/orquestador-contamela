from __future__ import annotations

import hashlib
import math
import re
from typing import Any


EMBEDDING_DIMS = 256
_TOKEN_PATTERN = re.compile(r"\w+|[^\w\s]", re.UNICODE)


def build_embeddings_response(input_value: Any, model: str) -> dict[str, Any]:
    texts = _normalize_embedding_input(input_value)
    data = []
    total_tokens = 0
    for index, text in enumerate(texts):
        vector = _embed_text(text)
        total_tokens += _estimate_tokens(text)
        data.append(
            {
                "object": "embedding",
                "index": index,
                "embedding": vector,
            }
        )
    return {
        "object": "list",
        "data": data,
        "model": model,
        "usage": {
            "prompt_tokens": total_tokens,
            "total_tokens": total_tokens,
        },
    }


def _normalize_embedding_input(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        normalized: list[str] = []
        for item in value:
            if isinstance(item, str):
                normalized.append(item)
            elif isinstance(item, list):
                normalized.append(" ".join(str(part) for part in item))
            else:
                normalized.append(str(item))
        return normalized
    raise ValueError("Formato de input no soportado para /v1/embeddings")


def _embed_text(text: str) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMS
    tokens = _TOKEN_PATTERN.findall(text.lower())
    if not tokens:
        return vector

    for token in tokens:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=16).digest()
        bucket = int.from_bytes(digest[:2], "big") % EMBEDDING_DIMS
        sign = 1.0 if digest[2] % 2 == 0 else -1.0
        magnitude = 1.0 + (digest[3] / 255.0)
        vector[bucket] += sign * magnitude

    norm = math.sqrt(sum(component * component for component in vector))
    if norm == 0:
        return vector
    return [round(component / norm, 8) for component in vector]


def _estimate_tokens(text: str) -> int:
    return max(1, len(_TOKEN_PATTERN.findall(text)))