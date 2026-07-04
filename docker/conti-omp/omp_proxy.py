#!/usr/bin/env python3
"""
omp_proxy.py — Proxy NDJSON limpio entre TCP y omp subprocess.

Reemplaza a omp_bridge.py + socat. El flujo es:
  1. Escucha en :7891 TCP
  2. Por cada conexión, fork+exec omp --mode=rpc
  3. Proxy NDJSON: TCP→stdin de omp, stdout de omp→TCP
  4. stderr va a un pipe separado (logs, NO al socket)

Esto garantiza que el stream TCP solo contenga NDJSON limpio,
sin bytes de stderr de Bun/Runtime mezclados.
"""

import json
import os
import select
import signal
import socket
import subprocess
import sys
import threading
import time

HOST = os.getenv("OMP_HOST", "0.0.0.0")
PORT = int(os.getenv("OMP_PORT", "7891"))
PROFILE = os.getenv("OMP_PROFILE", "conti")
OMP_MODEL = os.getenv("OMP_MODEL", "mistral/mistral-small-latest")
OMP_API_KEY = os.getenv("OMP_API_KEY", "")
OMP_PROVIDER = os.getenv("OMP_PROVIDER", "")
CWD = os.getenv("OMP_CIRCUIT_CWD", "/desarrollo")
PROMPT_TIMEOUT = float(os.getenv("OMP_PROMPT_TIMEOUT", "360"))


def log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [omp_proxy] {msg}", file=sys.stderr, flush=True)


def handle_client(conn: socket.socket, addr: tuple) -> None:
    """Maneja una conexión TCP: proxy NDJSON entre socket y omp subprocess."""
    log(f"connection from {addr}, cwd={CWD}, model={OMP_MODEL}")

    # Detectar provider
    provider = OMP_PROVIDER
    if not provider:
        if "/" in OMP_MODEL:
            provider = OMP_MODEL.split("/")[0]
        else:
            provider = "openai"

    cmd = [
        "/usr/local/bin/omp",
        "--mode",
        "rpc",
        f"--profile={PROFILE}",
        "--no-rules",
        "--no-title",
        f"--model={OMP_MODEL}",
        f"--api-key={OMP_API_KEY}",
        f"--provider={provider}",
    ]

    # Pipes separados para stdin/stdout/stderr
    stdin_r, stdin_w = os.pipe()
    stdout_r, stdout_w = os.pipe()
    stderr_r, stderr_w = os.pipe()

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=CWD,
            stdin=stdin_r,
            stdout=stdout_w,
            stderr=stderr_w,
            bufsize=0,
        )

        # Cerrar los ends que el padre no usa
        os.close(stdin_r)
        os.close(stdout_w)
        os.close(stderr_w)

        # Thread 1: stderr → log
        def drain_stderr():
            try:
                with os.fdopen(stderr_r, "r", errors="replace") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            log(f"[omp:stderr] {line[:200]}")
            except Exception:
                pass

        t_err = threading.Thread(target=drain_stderr, daemon=True)
        t_err.start()

        # Thread 2: omp stdout → TCP socket
        def omp_to_socket():
            try:
                with os.fdopen(stdout_r, "rb") as f:
                    while True:
                        data = f.read(65536)
                        if not data:
                            break
                        try:
                            conn.sendall(data)
                        except (BrokenPipeError, ConnectionResetError, OSError):
                            break
            except Exception:
                pass

        t_out = threading.Thread(target=omp_to_socket, daemon=True)
        t_out.start()

        # Thread principal: TCP socket → omp stdin
        try:
            while True:
                data = conn.recv(65536)
                if not data:
                    break
                os.write(stdin_w, data)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            try:
                os.close(stdin_w)
            except OSError:
                pass

        # Esperar a que omp termine
        proc.wait()
        log(f"omp subprocess exited with code {proc.returncode}")

    except Exception as exc:
        log(f"error: {exc}")
    finally:
        try:
            os.close(stdin_w)
        except OSError:
            pass
        try:
            os.close(stdout_r)
        except OSError:
            pass
        try:
            os.close(stderr_r)
        except OSError:
            pass
        try:
            conn.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        conn.close()


def main() -> None:
    if not OMP_API_KEY:
        log("FATAL: OMP_API_KEY not set")
        sys.exit(1)

    os.makedirs(CWD, exist_ok=True)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((HOST, PORT))
    sock.listen(8)
    log(f"listening on {HOST}:{PORT} (cwd={CWD}, model={OMP_MODEL})")

    signal.signal(signal.SIGCHLD, signal.SIG_IGN)

    while True:
        try:
            conn, addr = sock.accept()
        except KeyboardInterrupt:
            log("shutting down on SIGINT")
            break
        pid = os.fork()
        if pid == 0:
            sock.close()
            handle_client(conn, addr)
            os._exit(0)
        else:
            conn.close()

    sock.close()


if __name__ == "__main__":
    main()
