#!/usr/bin/env bash
# Write the Go2 scene-matched Foxglove layout (follow frame = base).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
OUT="${1:-/tmp/openral_layout_go2.json}"
cd "$ROOT"
PYTHONPATH=packages/openral_foxglove_bringup \
  python -m openral_foxglove_bringup.layout \
  --cameras top front --compressed --follow-frame base -o "$OUT"
# Side orbit + world-frame floor. Grid must be `world` at z=0 (Hub stand
# puts `base` at z≈0.27). A grid on `base` rides at chest height.
python3 - <<PY
import json
from pathlib import Path
path = Path("$OUT")
data = json.loads(path.read_text())
side = {
    "perspective": True,
    "distance": 2.2,
    "phi": 75.0,
    "thetaOffset": 90.0,
    "targetOffset": [0.0, 0.0, 0.15],
    "fovy": 45,
    "near": 0.05,
    "far": 5000,
}
floor = {
    "visible": True,
    "frameLocked": True,
    "label": "Floor",
    "instanceId": "go2-floor",
    "layerId": "foxglove.Grid",
    "frameId": "world",
    "divisions": 16,
    "lineWidth": 1,
    "color": "#9aa3b2",
    "size": 8,
    "position": [0, 0, 0],
    "rotation": [0, 0, 0],
    "order": 1,
}
for key in ("3D!scene", "3D!bucket2"):
    panel = data.get("configById", {}).get(key)
    if isinstance(panel, dict):
        panel["cameraState"] = side
        scene = panel.setdefault("scene", {})
        transforms = scene.setdefault("transforms", {})
        transforms["showLabel"] = False
        transforms["axisScale"] = 0
        layers = panel.setdefault("layers", {})
        layers["go2-floor"] = floor
path.write_text(json.dumps(data, indent=2) + "\n")
print(f"wrote {path} (followTf=base, view=side, axisScale=0, floor=world, compressed)")
PY
