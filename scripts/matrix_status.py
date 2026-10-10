#!/usr/bin/env python3
"""Send a one-letter status to the agent-button daemon."""

import socket
import sys
from pathlib import Path

SOCKET_PATH = Path.home() / ".grok" / "agent-button" / "status.sock"


def ping_daemon() -> bool:
    if not SOCKET_PATH.exists():
        return False
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        client.connect(str(SOCKET_PATH))
        client.sendall(b"?")
        reply = client.recv(16).decode("utf-8", errors="ignore").strip()
        return reply == "ok"
    except Exception:
        return False
    finally:
        client.close()


def send_status(status_char: str) -> bool:
    if not SOCKET_PATH.exists():
        print("agent-button daemon läuft nicht", file=sys.stderr)
        return False
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        client.connect(str(SOCKET_PATH))
        client.sendall(status_char.encode())
        reply = client.recv(16).decode("utf-8", errors="ignore").strip()
        return reply == "ok"
    except Exception as exc:
        print(f"status fehlgeschlagen: {exc}", file=sys.stderr)
        return False
    finally:
        client.close()


def main():
    if len(sys.argv) != 2:
        print("Usage: matrix_status.py <I|W|S|E|--ping>", file=sys.stderr)
        sys.exit(1)

    arg = sys.argv[1]
    if arg == "--ping":
        sys.exit(0 if ping_daemon() else 1)

    if arg not in "IWSE":
        print("Usage: matrix_status.py <I|W|S|E|--ping>", file=sys.stderr)
        sys.exit(1)

    sys.exit(0 if send_status(arg) else 1)


if __name__ == "__main__":
    main()