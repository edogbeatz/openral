"""Unit tests for ``openral viz mujoco`` kinematic apply (no GLFW window)."""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from openral_cli.viz import apply_qpos, fetch_qpos, resolve_viz_mjcf
from openral_core.exceptions import ROSConfigError

_FREE_HINGE_MJCF = """
<mujoco model="viz_qpos_contract">
  <worldbody>
    <body name="base" pos="0 0 0.3">
      <freejoint name="root"/>
      <geom type="box" size="0.05 0.05 0.05"/>
      <body name="link" pos="0 0 0">
        <joint name="hinge" type="hinge" axis="0 1 0"/>
        <geom type="capsule" size="0.02" fromto="0 0 0  0 0 -0.2"/>
      </body>
    </body>
  </worldbody>
</mujoco>
"""


def test_apply_qpos_forwards_without_stepping() -> None:
    mujoco = pytest.importorskip("mujoco")
    model = mujoco.MjModel.from_xml_string(_FREE_HINGE_MJCF)
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    t0 = float(data.time)
    qpos = [0.5, -0.25, 0.4, 1.0, 0.0, 0.0, 0.0, -0.8]
    assert len(qpos) == int(model.nq)
    apply_qpos(model, data, qpos, mujoco=mujoco)
    assert list(data.qpos) == pytest.approx(qpos)
    assert float(data.time) == t0  # mj_forward must not advance sim time


def test_apply_qpos_rejects_nq_mismatch() -> None:
    mujoco = pytest.importorskip("mujoco")
    model = mujoco.MjModel.from_xml_string(_FREE_HINGE_MJCF)
    data = mujoco.MjData(model)
    with pytest.raises(ROSConfigError, match=r"model\.nq"):
        apply_qpos(model, data, [0.0], mujoco=mujoco)


def test_resolve_viz_mjcf_go2_matches_menagerie_nq() -> None:
    pytest.importorskip("mujoco")
    pytest.importorskip("robot_descriptions")
    robot_yaml = Path("robots/go2/robot.yaml")
    if not robot_yaml.is_file():
        pytest.skip("robots/go2/robot.yaml not in cwd")
    mjcf = resolve_viz_mjcf(robot_yaml=robot_yaml)
    import mujoco

    model = mujoco.MjModel.from_xml_path(str(mjcf))
    assert int(model.nq) == 19  # 7 free + 12 actuated


def test_fetch_qpos_204_then_json_body() -> None:
    """A real local HTTP server: 204 is empty, 200 is the pose object."""
    state = {"empty": True}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path.rstrip("/") != "/api/qpos":
                self.send_error(404)
                return
            if state["empty"]:
                self.send_response(204)
                self.end_headers()
                return
            body = b'{"qpos":[0.1,0.2],"nq":2,"robot_id":"go2"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args: object) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}"
        assert fetch_qpos(url) is None
        state["empty"] = False
        got = fetch_qpos(url)
        assert got is not None
        assert got["nq"] == 2
        assert got["robot_id"] == "go2"
        assert got["qpos"] == [0.1, 0.2]
    finally:
        server.shutdown()
        thread.join(timeout=2.0)
