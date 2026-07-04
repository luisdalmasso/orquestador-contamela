"""
Test E2E real para el circuito `desarrollo`: Llamada HTTP real al emulador LLM.
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


def test_circuit_desarrollo_llamada_real_al_emulador():
    """Test E2E real: Llamada HTTP real al endpoint /v1/chat/completions del emulador LLM.

    Sin mocks. Verifica qué hace realmente el sistema cuando recibe esta request:
    - Detecta el circuito (debe ser 'desarrollo')
    - Crea una traza Ponytail
    - Intenta ejecutar el prompt (puede fallar si OpenHands SDK no está disponible)
    - Persiste la traza con el resultado real
    """
    # Configurar directorio de trazas para el circuito desarrollo
    ponytail_dir = Path("/desarrollo/.ponytail/traces")
    ponytail_dir.mkdir(parents=True, exist_ok=True)
    os.environ["PONYTAIL_TRACES_DIR"] = str(ponytail_dir)

    # Limpiar trazas previas
    for f in ponytail_dir.glob("trace-*.json"):
        f.unlink()

    # Hacer la llamada HTTP real al emulador LLM
    start_time = time.time()
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "mistral-small-latest",  # Será ignorado por el backend
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Explicame la app website del contenedor django "
                        "que paginas y servicios expone y documéntalo en un "
                        "archivo /desarrollo/django_website.md"
                    ),
                }
            ],
        },
        headers={"X-Circuit-ID": "desarrollo"},
    )
    elapsed = time.time() - start_time

    # Verificar que el endpoint respondió
    assert response.status_code in (200, 502), (
        f"Status inesperado: {response.status_code}"
    )
    result = response.json()

    # El sistema DEBE haber detectado el circuito 'desarrollo'
    assert "circuit" in result, f"El sistema debe reportar el circuito usado: {result}"
    assert result["circuit"] == "desarrollo", (
        f"Esperaba circuito 'desarrollo', obtuvo: {result.get('circuit')}"
    )

    # Verificar que se generó una traza Ponytail
    time.sleep(0.5)
    traces = list(ponytail_dir.glob("trace-*.json"))
    assert len(traces) >= 1, f"Debe haberse creado al menos una traza en {ponytail_dir}"

    latest_trace = max(traces, key=lambda p: p.stat().st_mtime)
    trace_data = json.loads(latest_trace.read_text())

    assert "events" in trace_data
    assert len(trace_data["events"]) > 0

    circuit_events = [
        e for e in trace_data["events"] if e.get("event") == "circuit_selected"
    ]
    assert len(circuit_events) > 0, f"No se encontró evento circuit_selected"
    assert circuit_events[0]["data"]["id"] == "desarrollo"

    print(f"\n✅ Traza generada: {latest_trace.name}")
    print(f"   Task: {trace_data.get('task_name')}")
    print(f"   Circuit: {circuit_events[0]['data']['id']}")
    print(f"   Workspace: {circuit_events[0]['data']['workspace']}")
    print(f"   Eventos: {len(trace_data['events'])}")
    print(f"   Duración HTTP: {elapsed:.2f}s")
    print(f"   Status del sistema: {result.get('status')}")
    if result.get("details"):
        print(f"   Detalles: {result.get('details')}")
