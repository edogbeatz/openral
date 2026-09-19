"""Generic sim camera rig.

Splice a robot's manifest-declared RGB cameras into a bare-arm MJCF that ships
no ``<camera>`` elements, so a ``deploy sim`` ``MujocoArmHAL``
twin renders the cameras the manifest declares — without a per-robot scene
composer or any ``scene_defaults.composition`` hook on the robot manifest.

Each RGB ``SensorSpec`` that carries a
``CameraSimPlacement`` and ``sim_render=True`` is spliced as a ``<camera>`` either
into its ``parent_body`` (a wrist camera that tracks the gripper) or into
``<worldbody>`` (a world-fixed overhead / third-person camera). The rig is
**idempotent**: a camera already present in the MJCF (a scene-attached or
already-composed model) is left untouched, so this composes cleanly with the
scene-attach path and prop composers (openarm).

The camera's MuJoCo name is ``sim_camera_name or name`` — the same key
``MujocoArmHAL.read_images`` renders — so the rig and the reader agree by
construction.
"""

from __future__ import annotations

import math
import re

from openral_core import SensorSpec
from openral_core.exceptions import ROSConfigError
from openral_core.geometry import look_at_quat_wxyz

__all__ = ["rig_cameras_into_mjcf"]


def _fovy_deg_for(sensor: SensorSpec) -> float:
    """Vertical FoV (degrees) for a sensor's sim camera.

    Uses ``sim_placement.fovy_deg`` when set, else derives it from the pinhole
    ``intrinsics`` (``2·atan(height / (2·fy))``) so the rendered FoV matches the
    declared camera model. Falls back to 60° when neither is available.
    """
    placement = sensor.sim_placement
    assert placement is not None  # caller guards
    if placement.fovy_deg is not None:
        return placement.fovy_deg
    intr = sensor.intrinsics
    if intr is None or intr.fy <= 0.0:
        return 60.0
    return math.degrees(2.0 * math.atan(intr.height / (2.0 * intr.fy)))


def _camera_element(sensor: SensorSpec) -> str:
    """Build the ``<camera>`` XML for one RGB sensor with a sim placement."""
    placement = sensor.sim_placement
    assert placement is not None  # caller guards
    name = sensor.sim_camera_name or sensor.name
    px, py, pz = placement.pos
    # MuJoCo cameras look along local -Z; orient -Z from pos toward target.
    # ``up`` levels the roll (``(0, 0, -1)`` for an upside-down-mounted camera).
    w, x, y, z = look_at_quat_wxyz(placement.pos, placement.target, up=placement.up, view_axis="-z")
    fovy = _fovy_deg_for(sensor)
    return (
        f'<camera name="{name}" pos="{px} {py} {pz}" '
        f'quat="{w} {x} {y} {z}" fovy="{fovy}" mode="fixed"/>'
    )


# Visual-only infinite checker floor + gradient sky. A flat gray patch under
# a black void made Foxglove's Image panel look "zoomed in" (the black sky
# vanished into the panel chrome; only the slab remained). Checker + skybox
# are still parameterless deploy staging, not task props — same menagerie
# ``scene.xml`` pattern. ``contype=0 conaffinity=0`` so the floor never
# contacts the robot or the safety kernel.
_STAGING_SKYBOX = (
    '<texture name="camrig_skybox" type="skybox" builtin="gradient" '
    'rgb1="0.3 0.5 0.7" rgb2="0 0 0" width="512" height="3072"/>'
)
_STAGING_GROUND_TEX = (
    '<texture name="camrig_ground" type="2d" builtin="checker" mark="edge" '
    'rgb1="0.55 0.58 0.62" rgb2="0.28 0.31 0.36" markrgb="0.75 0.75 0.75" '
    'width="300" height="300"/>'
)
_STAGING_GROUND_MAT = (
    '<material name="camrig_ground" texture="camrig_ground" '
    'texuniform="true" texrepeat="5 5" reflectance="0.2"/>'
)
_STAGING_FLOOR = (
    '<geom name="camrig_floor" type="plane" size="0 0 0.1" pos="0 0 0" '
    'material="camrig_ground" contype="0" conaffinity="0"/>'
)
_STAGING_VISUAL = (
    "\n  <visual>\n"
    '    <headlight ambient="0.45 0.45 0.45" diffuse="0.55 0.55 0.55" '
    'specular="0.1 0.1 0.1"/>\n'
    '    <rgba haze="0.15 0.25 0.35 1"/>\n'
    "  </visual>"
)


def _inject_asset_elements(xml: str, elements: str) -> str:
    """Insert ``elements`` into an existing ``<asset>``, or create one."""
    out, n = re.subn(r"(<asset\b[^>]*>)", rf"\1\n    {elements}", xml, count=1)
    if n == 1:
        return out
    out, n = re.subn(r"(<worldbody\b)", rf"<asset>\n    {elements}\n  </asset>\n  \1", xml, count=1)
    return out if n == 1 else xml


def _ensure_staging(xml: str) -> str:
    """Add minimal deploy-twin staging — a textured floor + sky + fill light.

    A bare arm MJCF ships no floor and (often) no lighting, so a gripper-mounted
    camera looking into the workspace renders pure black/void. This adds:

    - a **visual-only** infinite checker ground plane (no collisions) when the
      MJCF has no ``type="plane"`` geom — universal, parameterless deploy
      staging, not task props (CLAUDE.md: keep scene props in scene files);
    - a gradient skybox + haze and a moderate ambient ``<visual><headlight>``
      when no ``<visual>`` block exists, so the upper half of a forward camera
      is sky rather than void that Foxglove's dark Image panel swallows.

    Both are no-ops when the MJCF already declares them (a composed/scene MJCF
    set its own), so the rig composes with those rather than clobbering them.
    """
    if 'type="plane"' not in xml:
        xml = _inject_asset_elements(xml, f"{_STAGING_GROUND_TEX}\n    {_STAGING_GROUND_MAT}")
        xml, n = re.subn(r"(</worldbody>)", f"        {_STAGING_FLOOR}\n      \\1", xml, count=1)
        if n != 1:  # no worldbody to stage into — leave the model as-is
            pass
    if "<visual" not in xml:
        xml = _inject_asset_elements(xml, _STAGING_SKYBOX)
        out, n = re.subn(r"(<mujoco\b[^>]*>)", r"\1" + _STAGING_VISUAL, xml, count=1)
        if n == 1:
            xml = out
    return xml


def rig_cameras_into_mjcf(xml: str, sensors: list[SensorSpec]) -> tuple[str, bool]:
    """Splice each RGB sensor's missing sim camera into ``xml``; return ``(xml, changed)``.

    For every RGB ``SensorSpec`` with a ``CameraSimPlacement``
    whose camera name is absent from ``xml``, splice a ``<camera>`` into the
    named ``parent_body`` (or ``<worldbody>`` when ``parent_body`` is ``None``)
    and ensure checker-floor + skybox staging plus a fill light. Cameras already
    present are skipped (idempotent), so
    a scene-attached or already-composed MJCF passes through unchanged
    (``changed=False``) and the caller can load the original file.

    Raises:
        ROSConfigError: A sensor's ``parent_body`` is not found in the MJCF, or
            ``</worldbody>`` is missing for a world-fixed camera — the splice
            anchors are wrong and must surface loudly, not render a blank frame.
    """
    existing = set(re.findall(r'<camera[^>]*\bname="([^"]+)"', xml))
    rigged = [
        s
        for s in sensors
        if s.modality == "rgb"
        and s.sim_render
        and s.sim_placement is not None
        and (s.sim_camera_name or s.name) not in existing
    ]
    if not rigged:
        return xml, False

    world_cams: list[str] = []
    body_cams: dict[str, list[str]] = {}
    for s in rigged:
        placement = s.sim_placement
        assert placement is not None  # filtered above
        if placement.parent_body is None:
            world_cams.append(_camera_element(s))
        else:
            body_cams.setdefault(placement.parent_body, []).append(_camera_element(s))

    for body, cams in body_cams.items():
        snippet = "".join(f"\n        {c}" for c in cams)
        pattern = re.compile(rf'(<body[^>]*\bname="{re.escape(body)}"[^>]*>)')
        xml, n = pattern.subn(rf"\g<1>{snippet}", xml, count=1)
        if n != 1:
            raise ROSConfigError(
                f'camera rig: cannot find <body name="{body}"> to mount the wrist '
                f"camera(s) {[c.split(chr(34))[1] for c in cams]}. Check the sensor's "
                "sim_placement.parent_body matches an MJCF body name.",
            )

    if world_cams:
        snippet = "".join(f"\n        {c}" for c in world_cams)
        xml, n = re.subn(r"(</worldbody>)", f"{snippet}\n      \\1", xml, count=1)
        if n != 1:
            raise ROSConfigError(
                "camera rig: cannot find </worldbody> to mount the world-fixed "
                "camera(s) — the MJCF has no worldbody to splice into.",
            )

    return _ensure_staging(xml), True
