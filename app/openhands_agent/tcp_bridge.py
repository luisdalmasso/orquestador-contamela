#!/usr/bin/env python3
"""
tcp_bridge.py — Bridge simple entre stdio y TCP socket.
Reemplaza a socat para evitar bytes extra en el stream NDJSON.

Uso: python3 tcp_bridge.py <host> <port>
Conecta stdin→TCP y TCP→stdout, sin transformación.
"""

import os
import socket
import sys
import threading


def main():
    host = sys.argv[1] if len(sys.argv) > 1 else "conti-omp"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 7891

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))

    # Thread: TCP → stdout
    def forward_to_stdout():
        try:
            while True:
                data = sock.recv(65536)
                if not data:
                    break
                os.write(1, data)  # fd 1 = stdout
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    t = threading.Thread(target=forward_to_stdout, daemon=True)
    t.start()

    # Main thread: stdin → TCP
    try:
        while True:
            data = os.read(0, 65536)  # fd 0 = stdin
            if not data:
                break
            sock.sendall(data)
    except (BrokenPipeError, ConnectionResetError, OSError):
        pass
    finally:
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        sock.close()


if __name__ == "__main__":
    main()
