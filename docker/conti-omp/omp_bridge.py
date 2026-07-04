#!/usr/bin/env python3
"""
omp_bridge.py — Mini server TCP + spawn omp subprocess per-connection.

Reemplaza socat + omp_bridge (wrapper) por un solo proceso Python que:
  1. Escucha en :7891 TCP.
  2. Por cada conexión entrante, fork (vía os.fork).
  3. En el child: hace chdir a OMP_CIRCUIT_CWD, setea env vars, y hace
     `exec omp --mode=rpc`. El fd TCP queda como stdin/stdout/stderr.
  4. En el parent: cierra el fd TCP y vuelve a esperar conexiones.

Protocol: el cliente RpcClient abre TCP al :7891. El bridge hace chdir al
OMP_CIRCUIT_CWD (pasado via env por RpcClient al spawn del bridge
subprocess via socat-like o directamente), y omp subprocess recibe el
tráfico NDJSON por stdin/stdout.

Limitaciones:
- Single-process. Si omp crashea, la conexión termina. RpcClient
  debería reconectar.
- Multi-circuit: este bridge setea cwd al startup. Para multi-circuit
  simultáneo, hace falta multi-container omp (Sprint 5).
"""

import os
import signal
import socket
import subprocess
import sys
import time

HOST = "0.0.0.0"
PORT = int(os.environ.get("OMP_BRIDGE_PORT", "7891"))
CWD = os.environ.get("OMP_CIRCUIT_CWD", "/desarrollo")
PROFILE = os.environ.get("OMP_PROFILE", "conti")
OMP_MODEL = os.environ.get("OMP_MODEL", "mistral/mistral-small-latest")
OMP_API_KEY = os.environ.get("OMP_API_KEY", "")
OMP_PLAN = os.environ.get("OMP_PLAN", "0")
OMP_PROVIDER = os.environ.get("OMP_PROVIDER", "")


def log(msg: str) -> None:
    ts = time.strftime("%H:%M:%S")
    print(f"[omp_bridge {ts}] {msg}", file=sys.stderr, flush=True)


def detect_provider(model: str) -> str:
    if model.startswith(("mistral/", "mistral-")) or "/mistral-" in model:
        return "mistral"
    if model.startswith(("anthropic/", "claude-")):
        return "anthropic"
    if model.startswith(("openai/", "gpt-")):
        return "openai"
    return "openai"


def handle_client(conn: socket.socket, addr: tuple) -> None:
    """Handler para una conexión entrante. Ejecuta omp subprocess con
    stdin/stdout/stderr = conn. Después de omp terminar, cierra conn."""
    log(f"connection from {addr}, cwd={CWD}, model={OMP_MODEL}")
    try:
        os.makedirs(CWD, exist_ok=True)
        os.chdir(CWD)
    except Exception as exc:
        log(f"chdir({CWD}) failed: {exc}")
        conn.close()
        return

    plan_flag = "--plan" if OMP_PLAN == "1" else ""
    provider = OMP_PROVIDER or detect_provider(OMP_MODEL)

    cmd = [
        "/usr/local/bin/omp",
        "--mode=rpc",
        f"--profile={PROFILE}",
        "--no-rules",
        "--no-title",
        f"--model={OMP_MODEL}",
        f"--api-key={OMP_API_KEY}",
        f"--provider={provider}",
        # NO --no-skills: omp carga skills automáticamente desde
        # /home/conti/.omp/profiles/conti/skills/
        # NO --tools: omp tiene TODAS sus tools nativas habilitadas.
        # Solo deshabilitar skills/tools cuando se tenga criterio
        # basado en tests reales con skills custom.
    ]
    if plan_flag:
        cmd.append(plan_flag)

    # CRITICAL: stderr debe ir a un pipe separado, NO al socket TCP.
    # Si stderr va al mismo fd que stdout, los logs de Bun/Runtime se
    # mezclan con los mensajes NDJSON y rompen el parser de omp_rpc.
    stderr_r, stderr_w = os.pipe()

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=CWD,
            stdin=conn.fileno(),
            stdout=conn.fileno(),
            stderr=stderr_w,  # fd separado para stderr
            bufsize=0,
        )
        os.close(stderr_w)  # Cerrar el write end en el padre

        # Leer stderr en background y loguear (no bloquear el main thread)
        import threading

        def _drain_stderr():
            try:
                with os.fdopen(stderr_r, "r", errors="replace") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            log(f"[omp:stderr] {line[:200]}")
            except Exception:
                pass

        t = threading.Thread(target=_drain_stderr, daemon=True)
        t.start()

        proc.wait()
        log(f"omp subprocess exited with code {proc.returncode}")
    except Exception as exc:
        log(f"error spawning omp: {exc}")
        os.close(stderr_r)
    finally:
        try:
            conn.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        conn.close()


def main() -> None:
    if not OMP_API_KEY:
        log("FATAL: OMP_API_KEY not set")
        sys.exit(1)

    # Crear cwd si no existe.
    os.makedirs(CWD, exist_ok=True)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((HOST, PORT))
    sock.listen(8)
    log(f"listening on {HOST}:{PORT} (cwd={CWD}, model={OMP_MODEL})")

    # Manejo de SIGCHLD para evitar zombies.
    signal.signal(signal.SIGCHLD, signal.SIG_IGN)

    while True:
        try:
            conn, addr = sock.accept()
        except KeyboardInterrupt:
            log("shutting down on SIGINT")
            break
        pid = os.fork()
        if pid == 0:
            # Child
            sock.close()
            handle_client(conn, addr)
            os._exit(0)
        else:
            # Parent
            conn.close()

    sock.close()


if __name__ == "__main__":
    main()
