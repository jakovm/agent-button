#!/usr/bin/env bash
set -euo pipefail

export PATH="${HOME}/.local/bin:${PATH}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FQBN="m5stack:esp32:m5stack_atom"
SKETCH="${ROOT}/firmware/grok_companion"
PORT="${1:-/dev/cu.usbserial-855251E6E2}"

if ! command -v arduino-cli >/dev/null; then
  echo "arduino-cli nicht gefunden. Installiere es nach ~/.local/bin."
  exit 1
fi

echo "Kompiliere Firmware..."
arduino-cli compile --fqbn "${FQBN}" "${SKETCH}"

echo "Flashe nach ${PORT}..."
arduino-cli upload -p "${PORT}" --fqbn "${FQBN}" "${SKETCH}"

echo "Fertig."