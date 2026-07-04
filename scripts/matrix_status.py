#!/usr/bin/env python3
"""Send a one-letter status to the agent-button daemon."""

import socket
import sys
from pathlib import Path

SOCKET_PATH = Path.home() / ".grok" / "agent-button" / "status.sock"


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in "IWSE":
        print("Usage: matrix_status.py <I|W|S|E>", file=sys.stderr)
        sys.exit(1)

    if not SOCKET_PATH.exists():
        print("agent-button daemon läuft nicht", file=sys.stderr)
        sys.exit(1)

    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        client.connect(str(SOCKET_PATH))
        client.sendall(sys.argv[1].encode())
        reply = client.recv(16).decode("utf-8", errors="ignore").strip()
        sys.exit(0 if reply == "ok" else 1)
    except Exception as exc:
        print(f"status fehlgeschlagen: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        client.close()


if __name__ == "__main__":
    main()