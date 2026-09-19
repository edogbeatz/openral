#!/usr/bin/env bash
# Open Foxglove desktop on the Mac-forwarded cricket websocket.
# Layout import is still one picker step — Foxglove has no layout-import CLI.
# Docs: https://docs.foxglove.dev/docs/visualization/open-via-cli
set -euo pipefail
LAYOUT="${1:-/tmp/openral_layout_go2.json}"
# 127.0.0.1 not localhost — IPv6 ::1 can wedge, and Studio's error text
# quotes whatever is in the URL. Never pass layoutId (cloud sync 400
# "Invalid ID format" on a local / stale `lay_*`).
URL='foxglove://open?ds=foxglove-websocket&ds.url=ws://127.0.0.1:8765'
open "$URL"
echo "opened $URL"
echo "import layout: $LAYOUT"
echo "Foxglove → Layouts → + → Import from file → ⌘⇧G → $LAYOUT"
