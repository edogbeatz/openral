#!/usr/bin/env bash
# Open Foxglove desktop on the Mac-forwarded cricket websocket.
# Layout import is still one picker step — Foxglove has no layout-import CLI.
# Docs: https://docs.foxglove.dev/docs/visualization/open-via-cli
set -euo pipefail
LAYOUT="${1:-/tmp/openral_layout_go2.json}"
URL='foxglove://open?ds=foxglove-websocket&ds.url=ws://localhost:8765'
open "$URL"
echo "opened $URL"
echo "import layout: $LAYOUT"
echo "Foxglove → Layouts → + → Import from file → ⌘⇧G → $LAYOUT"
