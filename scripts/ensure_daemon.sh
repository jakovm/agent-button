#!/usr/bin/env bash
set -euo pipefail

STATE_DIR="${HOME}/.grok/agent-button"
PID_FILE="${STATE_DIR}/daemon.pid"
LOG_FILE="${STATE_DIR}/daemon.log"
STATUS_CLI="/Users/jakov/Documents/Smart Devices/scripts/matrix_status.py"
SOURCE_DAEMON="/Users/jakov/Documents/Smart Devices/scripts/matrix_daemon.py"
LOCAL_DAEMON="${STATE_DIR}/matrix_daemon.py"

mkdir -p "${STATE_DIR}"
cp "${SOURCE_DAEMON}" "${LOCAL_DAEMON}"

daemon_healthy() {
	[[ -S "${STATE_DIR}/status.sock" ]] || return 1
	python3 "${STATUS_CLI}" --ping >/dev/null 2>&1
}

stop_stale_daemon() {
	if [[ ! -f "${PID_FILE}" ]]; then
		return 0
	fi
	local pid
	pid="$(cat "${PID_FILE}")"
	if kill -0 "${pid}" 2>/dev/null; then
		kill "${pid}" 2>/dev/null || true
		for _ in 1 2 3 4 5 6 7 8 9 10; do
			kill -0 "${pid}" 2>/dev/null || break
			sleep 0.2
		done
	fi
	rm -f "${PID_FILE}" "${STATE_DIR}/status.sock"
}

if [[ -f "${PID_FILE}" ]]; then
	pid="$(cat "${PID_FILE}")"
	if kill -0 "${pid}" 2>/dev/null && daemon_healthy; then
		exit 0
	fi
	stop_stale_daemon
fi

nohup python3 -u "${LOCAL_DAEMON}" >>"${LOG_FILE}" 2>&1 &

for _ in 1 2 3 4 5 6 7 8 9 10; do
	if daemon_healthy && [[ -f "${PID_FILE}" ]]; then
		echo "agent-button daemon gestartet (pid $(cat "${PID_FILE}"))"
		exit 0
	fi
	sleep 0.5
done

echo "agent-button daemon konnte nicht gestartet werden" >&2
exit 1