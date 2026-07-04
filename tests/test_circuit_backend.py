"""
Test E2E real para el circuito `backend`: Llamada HTTP real al emulador LLM.
0 mocks. El test verifica qué pasa realmente cuando el sistema procesa esta request.
"""

import json
import os
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_circuit_backend_llamada_real_al_emulador():
    """Test E2E real: Llamada HTTP real al endpoint /v1/chat/completions del emulador LLM.

    Sin mocks. Verifica qué hace realmente el sistema cuando recibe esta request
    con el circuito 'backend' (workspace /contenedores/conti-backend).
    """
    # Configurar directorio de trazas para el circuito backend
    ponytail_dir = Path("/contenedores/conti-backend/.ponytail/traces")
    ponytail_dir.mkdir(parents=True, exist_ok=True)
    os.environ["PONYTAIL_TRACES_DIR"] = str(ponytail_dir)

    for f in ponytail_dir.glob("trace-*.json"):
        f.unlink()

    start_time = time.time()
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "mistral-small-latest",
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Analiza el endpoint /mcp del contenedor "
                        "conti-backend y documenta todas las tools en un "
                        "documento mcp_tools_doc.md"
                    ),
                }
            ],
        },
        headers={"X-Circuit-ID": "backend"},
    )
    elapsed = time.time() - start_time

    assert response.status_code in (200, 502), (
        f"Status inesperado: {response.status_code}"
    )
    result = response.json()

    assert "circuit" in result
    assert result["circuit"] == "backend", (
        f"Esperaba 'backend', obtuvo: {result.get('circuit')}"
    )

    time.sleep(0.5)
    traces = list(ponytail_dir.glob("trace-*.json"))
    assert len(traces) >= 1, f"Debe haberse creado al menos una traza"

    latest_trace = max(traces, key=lambda p: p.stat().st_mtime)
    trace_data = json.loads(latest_trace.read_text())

    assert "events" in trace_data
    assert len(trace_data["events"]) > 0

    circuit_events = [
        e for e in trace_data["events"] if e.get("event") == "circuit_selected"
    ]
    assert len(circuit_events) > 0
    assert circuit_events[0]["data"]["id"] == "backend"
    assert circuit_events[0]["data"]["workspace"] == "/contenedores/conti-backend"

    print(f"\n✅ Traza generada: {latest_trace.name}")
    print(f"   Task: {trace_data.get('task_name')}")
    print(f"   Circuit: {circuit_events[0]['data']['id']}")
    print(f"   Workspace: {circuit_events[0]['data']['workspace']}")
    print(f"   Eventos: {len(trace_data['events'])}")
    print(f"   Duración HTTP: {elapsed:.2f}s")
    print(f"   Status del sistema: {result.get('status')}")
