"""
Test E2E real para el circuito `produccion`: Llamada HTTP real al emulador LLM.
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


def test_circuit_produccion_llamada_real_al_emulador():
    """Test E2E real: Llamada HTTP real al endpoint /v1/chat/completions del emulador LLM.

    Sin mocks. Verifica qué hace realmente el sistema cuando recibe esta request
    con el circuito 'produccion' (workspace /compose).
    """
    # Configurar directorio de trazas para el circuito produccion (/compose)
    ponytail_dir = Path("/compose/.ponytail/traces")
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
                        "Analiza el contenedor chatui con definición en "
                        "producion.yml y documéntalo en un archivo chatui_doc.md"
                    ),
                }
            ],
        },
        headers={"X-Circuit-ID": "produccion"},
    )
    elapsed = time.time() - start_time

    assert response.status_code in (200, 502), (
        f"Status inesperado: {response.status_code}"
    )
    result = response.json()

    assert "circuit" in result
    assert result["circuit"] == "produccion", (
        f"Esperaba 'produccion', obtuvo: {result.get('circuit')}"
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
    assert circuit_events[0]["data"]["id"] == "produccion"
    assert circuit_events[0]["data"]["workspace"] == "/compose"

    print(f"\n✅ Traza generada: {latest_trace.name}")
    print(f"   Task: {trace_data.get('task_name')}")
    print(f"   Circuit: {circuit_events[0]['data']['id']}")
    print(f"   Workspace: {circuit_events[0]['data']['workspace']}")
    print(f"   Eventos: {len(trace_data['events'])}")
    print(f"   Duración HTTP: {elapsed:.2f}s")
    print(f"   Status del sistema: {result.get('status')}")
