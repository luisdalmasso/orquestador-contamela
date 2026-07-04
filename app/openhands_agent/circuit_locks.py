"""
app/openhands_agent/circuit_locks.py
====================================

Lock por circuit_id para serializar commits de traces del mismo circuit.
Permite paralelismo inter-circuit pero serializa intra-circuit.

Usado por `ponytail_record_trace` (en ponytail_trace_tools.py) cuando hace
git add + commit en background thread. Lock evita race conditions
cuando múltiples requests del mismo circuit terminan al mismo tiempo.

Sprint 4.3 / PLAN_3 §15.quinquies.5.
"""

from __future__ import annotations

import threading
from typing import Dict


_circuit_locks: Dict[str, threading.Lock] = {}
_locks_lock = threading.Lock()


def _get_lock(circuit_id: str) -> threading.Lock:
    """Devuelve un Lock dedicado por circuit_id. Thread-safe."""
    if circuit_id not in _circuit_locks:
        with _locks_lock:
            # double-check pattern
            if circuit_id not in _circuit_locks:
                _circuit_locks[circuit_id] = threading.Lock()
    return _circuit_locks[circuit_id]


def clear_locks() -> None:
    """Limpia todos los locks. Solo para tests."""
    global _circuit_locks
    _circuit_locks = {}
