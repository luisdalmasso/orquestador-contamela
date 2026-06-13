from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_translation_job_lifecycle(monkeypatch) -> None:
    from app.tools import translation_tools

    monkeypatch.setattr(
        translation_tools,
        "_translate_text",
        lambda source, target, text: f"[{target}] {text}",
    )

    docs_dir = Path(__file__).resolve().parents[1] / "docs"
    input_path = docs_dir / "tmp_translation_input.md"
    output_path = docs_dir / "tmp_translation_output-es.md"

    input_path.write_text("# Title\n\nHello world\n\nSecond paragraph.", encoding="utf-8")
    if output_path.exists():
        output_path.unlink()

    start_response = client.post(
        "/mcp/call",
        json={
            "tool": "start_markdown_translation",
            "arguments": {
                "input_path": str(input_path),
                "output_path": str(output_path),
                "target_lang": "es",
                "chunk_size": 500,
                "overwrite": True,
            },
        },
    )

    assert start_response.status_code == 200
    start_payload = start_response.json()
    assert start_payload["success"] is True
    job_id = start_payload["result"]["job_id"]

    status_payload = None
    for _ in range(50):
        time.sleep(0.05)
        status_response = client.post(
            "/mcp/call",
            json={
                "tool": "get_translation_job",
                "arguments": {
                    "job_id": job_id,
                },
            },
        )
        assert status_response.status_code == 200
        status_payload = status_response.json()
        if status_payload["result"]["status"] in {"completed", "failed"}:
            break

    assert status_payload is not None
    assert status_payload["result"]["status"] == "completed"
    assert output_path.exists()
    translated = output_path.read_text(encoding="utf-8")
    assert "[es]" in translated

    input_path.unlink(missing_ok=True)
    output_path.unlink(missing_ok=True)


def test_get_translation_job_requires_job_id() -> None:
    response = client.post(
        "/mcp/call",
        json={
            "tool": "get_translation_job",
            "arguments": {},
        },
    )
    assert response.status_code == 400
