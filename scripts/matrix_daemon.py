#!/usr/bin/env python3
"""Background daemon: Atom Matrix button + status display for Grok sessions."""

import glob
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import serial

DEFAULT_PORT = "/dev/cu.usbserial-855251E6E2"
BAUD_RATE = 115200
STATE_DIR = Path.home() / ".grok" / "agent-button"
PID_FILE = STATE_DIR / "daemon.pid"
SOCKET_PATH = STATE_DIR / "status.sock"
ACTIVE_SESSIONS = Path.home() / ".grok" / "active_sessions.json"

ser = None
status_lock = threading.Lock()
pending_idle_at = 0.0


def find_serial_port():
    if os.path.exists(DEFAULT_PORT):
        return DEFAULT_PORT
    matches = sorted(glob.glob("/dev/cu.usbserial-*"))
    return matches[0] if matches else None


def send_status(status_char):
    global pending_idle_at
    if ser is None:
        return False
    try:
        with status_lock:
            ser.write(status_char.encode())
            ser.flush()
        if status_char in ("S", "E"):
            pending_idle_at = time.time() + 4.0
        elif status_char == "I":
            pending_idle_at = 0.0
        return True
    except Exception:
        return False


def connect_matrix():
    global ser
    port = find_serial_port()
    if not port:
        print("agent-button: kein Serial-Port gefunden", file=sys.stderr)
        return False
    try:
        ser = serial.Serial(port, BAUD_RATE, timeout=0.1)
        time.sleep(1.5)
        send_status("I")
        print(f"agent-button: verbunden mit {port}")
        return True
    except Exception as exc:
        print(f"agent-button: serial fehlgeschlagen ({exc})", file=sys.stderr)
        return False


def abort_active_grok():
    env = os.environ.copy()
    env["PATH"] = f"{Path.home()}/.local/bin:{Path.home()}/.grok/bin:" + env.get("PATH", "")

    subprocess.run(
        ["grok", "leader", "kill"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if ACTIVE_SESSIONS.exists():
        try:
            sessions = json.loads(ACTIVE_SESSIONS.read_text())
            for entry in sessions:
                pid = entry.get("pid")
                if isinstance(pid, int) and pid > 0:
                    try:
                        os.kill(pid, signal.SIGINT)
                    except ProcessLookupError:
                        pass
                    except PermissionError:
                        pass
        except Exception:
            pass

    subprocess.run(
        ["pkill", "-INT", "-f", "grok"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def matrix_button_listener():
    while True:
        try:
            if ser is None:
                time.sleep(0.2)
                continue
            if ser.in_waiting > 0:
                line = ser.readline().decode("utf-8", errors="ignore").strip()
                if line == "BUTTON_PRESSED":
                    print("agent-button: Notbremse gedrückt")
                    abort_active_grok()
                    send_status("E")
        except Exception:
            time.sleep(0.5)


def idle_watchdog():
    while True:
        time.sleep(0.5)
        if pending_idle_at and time.time() >= pending_idle_at:
            send_status("I")


def socket_listener():
    if SOCKET_PATH.exists():
        SOCKET_PATH.unlink()
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(SOCKET_PATH))
    server.listen(5)
    os.chmod(SOCKET_PATH, 0o600)

    while True:
        conn, _ = server.accept()
        with conn:
            data = conn.recv(8).decode("utf-8", errors="ignore").strip()
            if data and data[0] in "IWSE":
                ok = send_status(data[0])
                conn.sendall(b"ok\n" if ok else b"err\n")


def write_pid():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))


def main():
    if not connect_matrix():
        sys.exit(1)

    write_pid()
    threading.Thread(target=matrix_button_listener, daemon=True).start()
    threading.Thread(target=idle_watchdog, daemon=True).start()
    threading.Thread(target=socket_listener, daemon=True).start()

    print(f"agent-button: daemon bereit (pid {os.getpid()})")
    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()