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
STATUS_FILE = STATE_DIR / "current_status"
ACTIVE_SESSIONS = Path.home() / ".grok" / "active_sessions.json"

ser = None
status_lock = threading.Lock()
pending_idle_at = 0.0


def load_persisted_status() -> str:
    try:
        if STATUS_FILE.exists():
            value = STATUS_FILE.read_text(encoding="utf-8").strip()
            if value in "IWSE":
                return value
    except Exception:
        pass
    return "I"


current_status = load_persisted_status()


def persist_status(status_char: str) -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        STATUS_FILE.write_text(status_char, encoding="utf-8")
    except Exception:
        pass


def find_serial_port():
    if os.path.exists(DEFAULT_PORT):
        return DEFAULT_PORT
    matches = sorted(glob.glob("/dev/cu.usbserial-*"))
    return matches[0] if matches else None


def disconnect_matrix():
    global ser
    if ser is None:
        return
    try:
        ser.close()
    except Exception:
        pass
    ser = None


def send_status(status_char, *, _retry=True):
    global current_status, pending_idle_at
    if ser is None and not connect_matrix():
        return False
    try:
        with status_lock:
            ser.write(status_char.encode())
            ser.flush()
        current_status = status_char
        persist_status(status_char)
        if status_char == "E":
            pending_idle_at = time.time() + 4.0
        else:
            pending_idle_at = 0.0
        print(f"agent-button: status → {status_char}")
        return True
    except Exception:
        disconnect_matrix()
        if _retry:
            return send_status(status_char, _retry=False)
        return False


def connect_matrix():
    global ser, pending_idle_at
    port = find_serial_port()
    if not port:
        return False
    restore = current_status
    try:
        disconnect_matrix()
        ser = serial.Serial(port, BAUD_RATE, timeout=0.1)
        time.sleep(1.5)
        with status_lock:
            ser.write(restore.encode())
            ser.flush()
        pending_idle_at = 0.0
        print(f"agent-button: verbunden mit {port} (status {restore})")
        return True
    except Exception as exc:
        disconnect_matrix()
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
            live_sessions = []
            for entry in sessions:
                pid = entry.get("pid")
                if not isinstance(pid, int) or pid <= 0:
                    continue
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    continue
                except PermissionError:
                    live_sessions.append(entry)
                    continue
                try:
                    os.kill(pid, signal.SIGINT)
                    live_sessions.append(entry)
                except ProcessLookupError:
                    pass
                except PermissionError:
                    live_sessions.append(entry)
            ACTIVE_SESSIONS.write_text(json.dumps(live_sessions, indent=2) + "\n")
        except Exception:
            pass


def handle_button_press():
    if current_status in ("I", "S"):
        print("agent-button: Button → Idle (kein Abbruch)")
        send_status("I")
        return
    print("agent-button: Notbremse gedrückt")
    abort_active_grok()
    send_status("E")


def matrix_button_listener():
    while True:
        try:
            if ser is None:
                connect_matrix()
                time.sleep(2.0)
                continue
            if ser.in_waiting > 0:
                line = ser.readline().decode("utf-8", errors="ignore").strip()
                if line == "BUTTON_PRESSED":
                    handle_button_press()
            else:
                time.sleep(0.05)
        except Exception:
            disconnect_matrix()
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
            if data == "?":
                conn.sendall(b"ok\n")
                continue
            if data and data[0] in "IWSE":
                ok = send_status(data[0])
                conn.sendall(b"ok\n" if ok else b"err\n")


def write_pid():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))


def main():
    write_pid()
    connect_matrix()
    threading.Thread(target=matrix_button_listener, daemon=True).start()
    threading.Thread(target=idle_watchdog, daemon=True).start()
    threading.Thread(target=socket_listener, daemon=True).start()

    print(f"agent-button: daemon bereit (pid {os.getpid()}, status {current_status})")
    while True:
        if ser is None:
            connect_matrix()
        time.sleep(30)


if __name__ == "__main__":
    main()