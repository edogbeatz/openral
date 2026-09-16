"""Generic ``SceneComposition`` composers for bare MuJoCo digital twins.

A ``deploy sim`` bare twin loads the robot's upstream MJCF as-is. That model
is usually just the robot: menagerie ships the terrain in a separate
``scene.xml`` wrapper that OpenRAL does not load. The HAL camera rig
(``openral_hal._camera_rig``) then splices in a checker plane so a forward
camera renders something other than void — but that plane is deliberately
``contype="0" conaffinity="0"``, visual only, so it never contacts the robot
or the safety kernel.

For a fixed-base arm, or a floating-base robot run with gravity off, nothing
notices. Turn gravity on for a legged robot and the consequence is immediate
and total: there is no ground, so the twin free-falls forever.

``compose_ground_plane_mjcf`` is the missing piece — a scene-declared,
robot-agnostic collidable floor:

.. code-block:: yaml

    composition:
      composer: "openral_sim.scene_composers:compose_ground_plane_mjcf"
      params:
        mjcf_ref: "rd:go2_mj_description"

Scene-level on purpose (CLAUDE.md — the robot manifest describes the robot,
the scene describes the scene): the same robot is a gravity-off contract
validator on one bench and a walking robot on another, and only the scene
knows which.
"""

from __future__ import annotations

import re
from pathlib import Path

from openral_core.assets import AssetRefError, resolve_asset
from openral_core.exceptions import ROSConfigError

__all__ = ["compose_ground_plane_mjcf"]

# Matches a plane geom that is NOT disabled for contacts. The camera rig's
# staging floor carries `contype="0" conaffinity="0"`, so a naive
# `type="plane"` test would see it and wrongly conclude the model already has
# ground. Attribute order inside a geom is not fixed, so the contact-disabling
# attributes are searched within the element rather than positionally.
_PLANE_GEOM = re.compile(r"<geom\b[^>]*\btype=\"plane\"[^>]*>|<geom\b[^>]*\btype=\"plane\"[^>]*/>")
_CONTACTS_OFF = re.compile(r"\bcon(type|affinity)=\"0\"")

_GROUND_TEX = (
    '<texture name="openral_ground" type="2d" builtin="checker" '
    'rgb1="0.2 0.3 0.4" rgb2="0.1 0.15 0.2" width="512" height="512"/>'
)
_GROUND_MAT = (
    '<material name="openral_ground" texture="openral_ground" '
    'texuniform="true" texrepeat="5 5" reflectance="0.1"/>'
)


def _has_collidable_plane(xml: str) -> bool:
    """Whether ``xml`` already declares a plane geom that participates in contacts."""
    return any(not _CONTACTS_OFF.search(m.group(0)) for m in _PLANE_GEOM.finditer(xml))


def _inject_asset_elements(xml: str, elements: str) -> str:
    """Append ``elements`` to the MJCF's ``<asset>`` block, creating one if absent."""
    out, n = re.subn(r"(</asset>)", f"    {elements}\n  \\1", xml, count=1)
    if n == 1:
        return out
    out, n = re.subn(r"(<worldbody\b)", rf"<asset>\n    {elements}\n  </asset>\n  \1", xml, count=1)
    return out if n == 1 else xml


def compose_ground_plane_mjcf(
    *,
    mjcf_ref: str,
    friction: tuple[float, float, float] = (1.0, 0.005, 0.0001),
    half_extent_m: float = 0.0,
    grid_spacing_m: float = 0.5,
) -> tuple[str, Path]:
    """Splice a **collidable** ground plane into a robot's upstream MJCF.

    Idempotent: a model that already has a contact-participating plane (a
    composed arena, a menagerie ``scene.xml``) is returned untouched, so
    stacking this on a scene that brought its own floor is a no-op rather
    than two overlapping planes fighting at z=0.

    Args:
        mjcf_ref: ``openral_core.assets.resolve_asset`` MJCF reference for the
            robot model to stage, e.g. ``"rd:go2_mj_description"``.
        friction: MuJoCo ``(sliding, torsional, rolling)`` friction for the
            plane. The default is MuJoCo's own geom default; a legged policy
            trained on flat terrain expects roughly unit sliding friction, and
            lowering it makes the robot skate.
        half_extent_m: Plane half-size in metres. ``0.0`` (default) makes the
            plane **infinite**, which is what a locomotion bench wants — a
            finite plane gives the robot an edge to walk off.
        grid_spacing_m: Spacing of the checker texture's repeat, in metres.
            Visual only; it also makes translation legible in a 3D view, where
            an untextured infinite plane gives the eye nothing to track.

    Returns:
        ``(xml, meshdir)`` per the ``SceneComposition`` contract — the composed
        MJCF and the directory relative mesh paths resolve against. The caller
        writes the XML to ``meshdir.parent`` so the model's own relative asset
        references keep working.

    Raises:
        ROSConfigError: ``mjcf_ref`` does not resolve to a file, or the model
            has no ``<worldbody>`` to stage into.

    Example:
        >>> xml, meshdir = compose_ground_plane_mjcf(
        ...     mjcf_ref="rd:go2_mj_description"
        ... )  # doctest: +SKIP
        >>> 'name="openral_ground"' in xml  # doctest: +SKIP
        True
    """
    # `AssetRefError` is translated here, matching `_mujoco_arm._resolve_mjcf`:
    # this composer is called by the HAL lifecycle node, and only `ROSError`
    # subclasses are meant to cross that boundary.
    try:
        resolved = resolve_asset(mjcf_ref, "mjcf")
    except AssetRefError as exc:
        raise ROSConfigError(
            f"compose_ground_plane_mjcf: mjcf_ref {mjcf_ref!r} did not resolve to a file ({exc})"
        ) from exc
    if resolved is None or not Path(resolved).is_file():
        raise ROSConfigError(
            f"compose_ground_plane_mjcf: mjcf_ref {mjcf_ref!r} did not resolve to a file "
            f"(got {resolved!r}); expected an `rd:` / `file:` / `menagerie:` MJCF reference."
        )
    path = Path(resolved)
    xml = path.read_text()
    # Meshes resolve against the model's own directory (menagerie models
    # declare `<compiler meshdir="assets"/>`), and the node writes the composed
    # file to `meshdir.parent` — i.e. back alongside the original model.
    meshdir = path.parent / "assets"

    if _has_collidable_plane(xml):
        return xml, meshdir

    size = f"{half_extent_m:g} {half_extent_m:g} {grid_spacing_m:g}"
    fric = " ".join(f"{v:g}" for v in friction)
    floor = (
        f'<geom name="openral_ground" type="plane" size="{size}" pos="0 0 0" '
        f'friction="{fric}" material="openral_ground"/>'
    )
    xml = _inject_asset_elements(xml, f"{_GROUND_TEX}\n    {_GROUND_MAT}")
    xml, n = re.subn(r"(</worldbody>)", f"    {floor}\n  \\1", xml, count=1)
    if n != 1:
        raise ROSConfigError(
            f"compose_ground_plane_mjcf: {path} has no <worldbody> to stage a ground plane "
            "into; it is not a loadable MuJoCo model."
        )
    return xml, meshdir
