#!/usr/bin/env bash
# Start the operator /simple app when asked. Agents must run this, not print it.
#
# 1. Reuse a live laptop collector on :4318, or `just dashboard` (write-controls).
# 2. POST /api/demo/cricket/start unless --dashboard-only (already-running is success).
# 3. Open http://127.0.0.1:4318/simple.
#
# Do not steal tunnels. Do not pkill the graph. Do not loop `brev start` on credits.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
DASHBOARD_URL="${OPENRAL_DASHBOARD_URL:-http://127.0.0.1:4318}"
SIMPLE="${DASHBOARD_URL}/simple"
HEALTHZ="${DASHBOARD_URL}/healthz"
LOG="${OPENRAL_DASHBOARD_LOG:-/tmp/openral-dashboard.log}"
CRICKET=1
OPEN_BROWSER=1

usage() {
  echo "usage: $0 [--dashboard-only] [--no-open]"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dashboard-only) CRICKET=0; shift ;;
    --no-open) OPEN_BROWSER=0; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
done

healthz_ok() {
  curl -sf --max-time 2 "$HEALTHZ" >/dev/null 2>&1
}

echo "repo $ROOT"
if healthz_ok; then
  echo "reusing $DASHBOARD_URL (healthz ok)"
else
  if [[ ! -f "${HOME}/.openral/dashboard.env" ]]; then
    echo "seeding ~/.openral/dashboard.env (once)"
    (cd "$ROOT" && just dashboard-acquire-env) || echo "Acquire env seed skipped; /simple chat may FAULT" >&2
  fi
  echo "starting just dashboard → $DASHBOARD_URL"
  (cd "$ROOT" && just dashboard) >>"$LOG" 2>&1 &
  for _ in $(seq 1 40); do
    healthz_ok && break
    sleep 0.5
  done
  if ! healthz_ok; then
    echo "dashboard did not become healthy on $HEALTHZ" >&2
    echo "log: $LOG" >&2
    tail -n 40 "$LOG" >&2 || true
    exit 1
  fi
fi

if [[ "$CRICKET" -eq 1 ]]; then
  echo "POST ${DASHBOARD_URL}/api/demo/cricket/start"
  code="$(
    curl -sS -o /tmp/openral-cricket-start.json -w "%{http_code}" --max-time 180 \
      -X POST "${DASHBOARD_URL}/api/demo/cricket/start" || echo "000"
  )"
  echo "start HTTP $code"
  cat /tmp/openral-cricket-start.json 2>/dev/null || true
  echo
  case "$code" in
    200|202) ;;
    403)
      echo "write-controls off; restart the collector with just dashboard" >&2
      exit 1
      ;;
    *)
      echo "cricket start failed. Append skill Troubleshooting / Start failures." >&2
      exit 1
      ;;
  esac
  python3 - "$DASHBOARD_URL" <<'PY'
import json, sys, time, urllib.error, urllib.request

base = sys.argv[1].rstrip("/")
url = f"{base}/api/demo/cricket"
deadline = time.time() + 180
last = ""
while time.time() < deadline:
    try:
        with urllib.request.urlopen(url, timeout=12) as resp:
            body = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        last = str(exc)
        time.sleep(3)
        continue
    err = body.get("start_error")
    running = bool(body.get("graph_running"))
    if running:
        print(f"graph_running true role={body.get('role')!r}")
        sys.exit(0)
    if err:
        print(json.dumps(body, indent=2), file=sys.stderr)
        sys.exit(1)
    last = json.dumps({k: body.get(k) for k in ("graph_running", "start_in_progress", "role")})
    time.sleep(3)
print(f"timed out waiting for graph_running; last={last}", file=sys.stderr)
sys.exit(1)
PY
fi

echo "open $SIMPLE"
if [[ "$OPEN_BROWSER" -eq 1 ]] && command -v open >/dev/null 2>&1; then
  open "$SIMPLE"
fi
