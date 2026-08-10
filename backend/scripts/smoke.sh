#!/usr/bin/env bash
# End-to-end smoke test against a running backend (default localhost:8000).
# Usage: scripts/smoke.sh [base_url]
set -euo pipefail
BASE="${1:-http://localhost:8000}"

check() {
  local path="$1" expect="${2:-200}"
  local code
  code=$(curl -s -o /dev/null -w '%{http_code}' "$BASE$path")
  if [[ "$code" != "$expect" ]]; then
    echo "FAIL $path -> $code (expected $expect)"
    exit 1
  fi
  echo "ok   $path -> $code"
}

check /api/health
check /api/feed
check /api/questions
check /api/brief
check /api/leaderboard
check /api/leaderboard/calibration
check /api/leaderboard/predictions
check /api/stats
check /api/categories
check /api/discover/candidates
check "/api/brief?count=0" 422
check /api/questions/99999 404

QID=$(curl -s "$BASE/api/questions" | python3 -c "import json,sys; print(json.load(sys.stdin)[-1]['id'])")
check "/api/questions/$QID"
check "/api/questions/$QID/history"
check "/api/cards/$QID.svg"

echo "smoke: all checks passed against $BASE"
