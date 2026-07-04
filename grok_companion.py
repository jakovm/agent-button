#!/usr/bin/env python3
"""Bridge between Grok CLI and the M5 Atom Matrix status display."""

import glob
import os
import pty
import select
import signal
import subprocess
import sys
import termios
import threading
import time
import tty

import serial

DEFAULT_PORT = "/dev/cu.usbserial-855251E6E2"
BAUD_RATE = 115200

grok_process = None
ser = None


def find_serial_port():
    if os.path.exists(DEFAULT_PORT):
        return DEFAULT_PORT
    matches = sorted(glob.glob("/dev/cu.usbserial-*"))
    return matches[0] if matches else None


def send_status(status_char):
    if ser is None:
        return
    try:
        ser.write(status_char.encode())
        ser.flush()
    except Exception:
        pass


def matrix_button_listener():
    global grok_process
    while True:
        try:
            if ser.in_waiting > 0:
                line = ser.readline().decode("utf-8", errors="ignore").strip()
                if line == "BUTTON_PRESSED":
                    if grok_process and grok_process.poll() is None:
                        print("\n[Atom Companion] Notbremse gedrückt — breche Grok ab...")
                        os.kill(grok_process.pid, signal.SIGINT)
                        send_status("E")
        except Exception:
            break


def connect_matrix():
    global ser
    port = find_serial_port()
    if not port:
        print("Fehler: Kein Atom-Matrix-Serial-Port gefunden.")
        print("Prüfe USB-Verbindung und schließe die Arduino IDE.")
        sys.exit(1)

    try:
        ser = serial.Serial(port, BAUD_RATE, timeout=0.1)
        time.sleep(2)
        send_status("I")
        print(f"[Companion] Verbunden mit Atom Matrix auf {port}")
    except Exception:
        print(f"Fehler: Verbindung zum Atom Matrix auf {port} fehlgeschlagen.")
        print("Prüfe USB-Verbindung oder ob die Arduino IDE den Port blockiert.")
        sys.exit(1)


def bridge_pty(master_fd):
    old_tty = termios.tcgetattr(sys.stdin)
    try:
        tty.setraw(sys.stdin.fileno())
        while True:
            if grok_process.poll() is not None:
                break
            readable, _, _ = select.select([master_fd, sys.stdin], [], [], 0.1)
            if master_fd in readable:
                try:
                    output = os.read(master_fd, 4096)
                except OSError:
                    break
                if not output:
                    break
                os.write(sys.stdout.fileno(), output)
            if sys.stdin in readable:
                try:
                    user_input = os.read(sys.stdin.fileno(), 4096)
                except OSError:
                    break
                if not user_input:
                    break
                os.write(master_fd, user_input)
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_tty)


def run_grok():
    global grok_process

    grok_args = sys.argv[1:]
    if not grok_args:
        grok_args = ["build"]

    print(f"[Companion] Starte 'grok {' '.join(grok_args)}'...")
    send_status("W")

    master_fd = None
    try:
        master_fd, slave_fd = pty.openpty()
        grok_process = subprocess.Popen(
            ["grok"] + grok_args,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            close_fds=True,
        )
        os.close(slave_fd)
        bridge_pty(master_fd)

        grok_process.wait()
        if grok_process.returncode == 0:
            print("\n[Companion] Grok erfolgreich beendet.")
            send_status("S")
        elif grok_process.returncode in (-signal.SIGINT, 2):
            print("\n[Companion] Durch Hardware-Button abgebrochen.")
            send_status("E")
        else:
            print(f"\n[Companion] Grok-Fehler (Exit Code: {grok_process.returncode})")
            send_status("E")
    except FileNotFoundError:
        print("\nFehler: 'grok' wurde im PATH nicht gefunden.")
        send_status("E")
    finally:
        if master_fd is not None:
            os.close(master_fd)
        time.sleep(4)
        send_status("I")


def main():
    connect_matrix()
    threading.Thread(target=matrix_button_listener, daemon=True).start()
    try:
        run_grok()
    finally:
        if ser and ser.is_open:
            ser.close()


if __name__ == "__main__":
    main()