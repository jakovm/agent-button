#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STATE_DIR="${HOME}/.grok/agent-button"
PID_FILE="${STATE_DIR}/daemon.pid"
LOG_FILE="${STATE_DIR}/daemon.log"

mkdir -p "${STATE_DIR}"

if [[ -f "${PID_FILE}" ]]; then
  pid="$(cat "${PID_FILE}")"
  if kill -0 "${pid}" 2>/dev/null; then
    exit 0
  fi
fi

nohup python3 "${ROOT}/scripts/matrix_daemon.py" >>"${LOG_FILE}" 2>&1 &

for _ in 1 2 3 4 5 6 7 8 9 10; do
  if [[ -S "${STATE_DIR}/status.sock" ]] && [[ -f "${PID_FILE}" ]]; then
    if kill -0 "$(cat "${PID_FILE}")" 2>/dev/null; then
      echo "agent-button daemon gestartet (pid $(cat "${PID_FILE}"))"
      exit 0
    fi
  fi
  sleep 0.5
done

echo "agent-button daemon konnte nicht gestartet werden" >&2
exit 1