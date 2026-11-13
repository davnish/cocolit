#!/bin/bash
# Re-run `tofu apply` until Oracle has A1 capacity.
# Usage: ./retry-apply.sh [seconds_between_tries]   (default 300)
# Stops on success, or on an error that is neither "Out of host capacity"
# nor a temporary network/API error.
set -uo pipefail
cd "$(dirname "$0")"

INTERVAL="${1:-300}"
LOG="$(mktemp -t cocolit-apply)"
attempt=0

while true; do
  attempt=$((attempt + 1))
  echo "[$(date '+%F %T')] attempt $attempt"
  tofu apply -auto-approve -input=false -no-color 2>&1 | tee "$LOG"
  status=${PIPESTATUS[0]}

  if [ "$status" -eq 0 ]; then
    echo "[$(date '+%F %T')] apply succeeded after $attempt attempt(s)"
    tofu output
    exit 0
  fi
  if grep -q "Out of host capacity" "$LOG"; then
    echo "[$(date '+%F %T')] no A1 capacity yet; retrying in ${INTERVAL}s"
  elif grep -qiE "EOF|timeout|connection reset|connection refused|no such host|TLS handshake|429|TooManyRequests|503|ServiceUnavailable" "$LOG"; then
    # Network blips and rate limits are temporary; keep going.
    echo "[$(date '+%F %T')] temporary network or API error; retrying in ${INTERVAL}s"
  else
    echo "[$(date '+%F %T')] apply failed for another reason; stopping (log: $LOG)" >&2
    exit "$status"
  fi
  sleep "$INTERVAL"
done
