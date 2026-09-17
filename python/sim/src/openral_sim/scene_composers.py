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
import xml.etree.ElementTree as ET
from pathlib import Path

from openral_core.assets import AssetRefError, resolve_asset
from openral_core.exceptions import ROSConfigError

__all__ = ["compose_ground_plane_mjcf", "compose_mounted_arm_mjcf"]

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
    path = _resolve_mjcf(mjcf_ref)
    xml = path.read_text()
    # Meshes resolve against the model's own directory (menagerie models
    # declare `<compiler meshdir="assets"/>`), and the node writes the composed
    # file to `meshdir.parent` — i.e. back alongside the original model.
    meshdir = path.parent / "assets"

    return _stage_ground(
        xml,
        friction=friction,
        half_extent_m=half_extent_m,
        grid_spacing_m=grid_spacing_m,
        source=str(path),
    ), meshdir


def _resolve_mjcf(mjcf_ref: str) -> Path:
    """Resolve an MJCF asset reference to a file, as a ``ROSError`` on failure.

    ``AssetRefError`` is translated here, matching ``_mujoco_arm._resolve_mjcf``:
    these composers are called by the HAL lifecycle node, and only ``ROSError``
    subclasses are meant to cross that boundary.
    """
    try:
        resolved = resolve_asset(mjcf_ref, "mjcf")
    except AssetRefError as exc:
        raise ROSConfigError(
            f"scene_composers: mjcf_ref {mjcf_ref!r} did not resolve to a file ({exc})"
        ) from exc
    if resolved is None or not Path(resolved).is_file():
        raise ROSConfigError(
            f"scene_composers: mjcf_ref {mjcf_ref!r} did not resolve to a file "
            f"(got {resolved!r}); expected an `rd:` / `file:` / `menagerie:` MJCF reference."
        )
    return Path(resolved)


def _stage_ground(
    xml: str,
    *,
    friction: tuple[float, float, float] = (1.0, 0.005, 0.0001),
    half_extent_m: float = 0.0,
    grid_spacing_m: float = 0.5,
    source: str = "<model>",
) -> str:
    """Splice a collidable ground plane into ``xml``; no-op when one already exists."""
    if _has_collidable_plane(xml):
        return xml
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
            f"scene_composers: {source} has no <worldbody> to stage a ground plane into; "
            "it is not a loadable MuJoCo model."
        )
    return xml


def _namespace_default_classes(arm_root: ET.Element, prefix: str) -> None:
    """Prefix every ``<default>`` class the arm declares, and its references.

    MuJoCo default-class names are **global**, not scoped to the model that
    declared them. Two menagerie models routinely both declare nested
    ``visual`` / ``collision`` classes, so merging them raises
    ``XML Error: repeated default class name``. Renaming only the arm's side
    keeps the base model's classes — and anything referring to them — untouched.
    """
    declared = {d.get("class") for d in arm_root.iter("default") if d.get("class")}
    for default in arm_root.iter("default"):
        name = default.get("class")
        if name:
            default.set("class", prefix + name)
    for element in arm_root.iter():
        for attr in ("class", "childclass"):
            value = element.get(attr)
            if value is not None and value in declared:
                element.set(attr, prefix + value)


def _absolutise_mesh_paths(arm_root: ET.Element, arm_dir: Path) -> None:
    """Rewrite the arm's ``<mesh file=...>`` to absolute paths.

    The composed model is written next to the BASE model, so the arm's own
    ``compiler/meshdir`` (relative to its own directory) no longer resolves.
    Absolute paths sidestep having to reconcile two ``meshdir`` roots.
    """
    compiler = arm_root.find("compiler")
    meshdir = arm_dir / ((compiler.get("meshdir") if compiler is not None else None) or ".")
    for mesh in arm_root.iter("mesh"):
        filename = mesh.get("file")
        if filename:
            mesh.set("file", str((meshdir / filename).resolve()))


def _merge_section(base_root: ET.Element, arm_root: ET.Element, tag: str) -> None:
    """Append the arm's ``<tag>`` children onto the base's, creating the block if absent."""
    arm_section = arm_root.find(tag)
    if arm_section is None:
        return
    base_section = base_root.find(tag)
    if base_section is None:
        base_section = ET.SubElement(base_root, tag)
    for child in list(arm_section):
        base_section.append(child)


def _scale_subtree_inertial(root: ET.Element, scale: float) -> None:
    """Multiply every ``<inertial>`` mass / inertia under ``root`` by ``scale``.

    Used so a locomotion policy trained on the bare carrier can stay upright
    with a visually-present arm whose full menagerie mass would tip it. Meshes
    and kinematics are unchanged — only the dynamic payload.
    """
    for body in root.iter("body"):
        inertial = body.find("inertial")
        if inertial is None:
            continue
        mass = inertial.get("mass")
        if mass is not None:
            inertial.set("mass", f"{float(mass) * scale:g}")
        diag = inertial.get("diaginertia")
        if diag is not None:
            vals = [float(x) * scale for x in diag.split()]
            inertial.set("diaginertia", " ".join(f"{v:g}" for v in vals))
        full = inertial.get("fullinertia")
        if full is not None:
            vals = [float(x) * scale for x in full.split()]
            inertial.set("fullinertia", " ".join(f"{v:g}" for v in vals))


def compose_mounted_arm_mjcf(
    *,
    base_mjcf_ref: str,
    arm_mjcf_ref: str,
    mount_body: str,
    mount_pos: tuple[float, float, float],
    arm_mjcf_file: str | None = None,
    mount_quat: tuple[float, float, float, float] | None = None,
    class_prefix: str = "arm__",
    ground: bool = True,
    arm_mass_scale: float = 1.0,
) -> tuple[str, Path]:
    """Bolt an arm MJCF onto a body of a base-robot MJCF; return ``(xml, meshdir)``.

    The composite a mobile-manipulation task needs — an arm on a quadruped, a
    gripper on a mobile base — without vendoring a hand-merged model. Both
    halves stay upstream menagerie assets, so a bump on either side flows
    through.

    The arm's kinematic tree is appended as the LAST child of ``mount_body``,
    which puts its joints after the base robot's in ``qpos`` order. That
    ordering is load-bearing: it leaves the base robot's existing joint
    indexing untouched, so a locomotion policy written against a 12-DoF Go2
    keeps working unchanged when an arm is added behind it.

    Three merge hazards are handled, each of which otherwise fails at compile:
    globally-scoped default-class name collisions, the arm's ``meshdir`` no
    longer resolving from the base model's directory, and keyframes whose
    ``qpos`` width must grow to the composite's joint count.

    Args:
        base_mjcf_ref: ``resolve_asset`` MJCF reference for the carrier robot,
            e.g. ``"rd:go2_mj_description"``.
        arm_mjcf_ref: ``resolve_asset`` MJCF reference for the arm package.
        mount_body: Body in the base model to attach the arm to (the Go2's
            ``base``). Raises if the model has no such body.
        mount_pos: ``(x, y, z)`` of the arm root in ``mount_body``'s frame.
        arm_mjcf_file: Sibling filename to prefer inside the arm package's
            directory — menagerie ships variants next to the main model
            (``z1_gripper.xml`` beside ``z1.xml``), and a gripper is the whole
            point for manipulation. ``None`` uses whatever the ref resolves to.
        mount_quat: Optional ``(w, x, y, z)`` orientation of the mount.
        class_prefix: Namespace applied to the arm's default classes.
        ground: Also stage a collidable floor (see
            :func:`compose_ground_plane_mjcf`). A composite under gravity needs
            one for the same reason a bare legged twin does.
        arm_mass_scale: Multiplier applied to every arm-subtree ``<inertial>``
            (mass + diagonal/full inertia). ``1.0`` keeps menagerie mass;
            values in ``(0, 1)`` shrink the dynamic payload so a bare-carrier
            locomotion policy can stay upright while the arm stays visible and
            kinematically held. Not a claim about real Go2+Z1 dynamics.

    Returns:
        ``(xml, meshdir)`` per the ``SceneComposition`` contract.

    Raises:
        ROSConfigError: Either ref fails to resolve, ``mount_body`` is absent,
            the arm model exposes no body to mount, or ``arm_mass_scale`` is
            not strictly positive.
    """
    if arm_mass_scale <= 0.0:
        raise ROSConfigError(
            f"compose_mounted_arm_mjcf: arm_mass_scale must be > 0 (got {arm_mass_scale})"
        )
    base_path = _resolve_mjcf(base_mjcf_ref)
    arm_path = _resolve_mjcf(arm_mjcf_ref)
    if arm_mjcf_file:
        candidate = arm_path.parent / arm_mjcf_file
        if not candidate.is_file():
            raise ROSConfigError(
                f"compose_mounted_arm_mjcf: arm_mjcf_file {arm_mjcf_file!r} not found beside "
                f"{arm_path} (looked at {candidate})"
            )
        arm_path = candidate

    base_root = ET.parse(base_path).getroot()
    arm_root = ET.parse(arm_path).getroot()

    _absolutise_mesh_paths(arm_root, arm_path.parent)
    _namespace_default_classes(arm_root, class_prefix)
    for tag in ("default", "asset", "actuator", "tendon", "equality", "contact", "sensor"):
        _merge_section(base_root, arm_root, tag)

    mount = next((b for b in base_root.iter("body") if b.get("name") == mount_body), None)
    if mount is None:
        raise ROSConfigError(
            f"compose_mounted_arm_mjcf: {base_path} has no body named {mount_body!r}; "
            "cannot mount the arm."
        )
    arm_body = arm_root.find("worldbody/body")
    if arm_body is None:
        raise ROSConfigError(f"compose_mounted_arm_mjcf: {arm_path} declares no body to mount.")
    if arm_mass_scale != 1.0:
        _scale_subtree_inertial(arm_body, arm_mass_scale)
    arm_body.set("pos", " ".join(f"{v:g}" for v in mount_pos))
    if mount_quat is not None:
        arm_body.set("quat", " ".join(f"{v:g}" for v in mount_quat))
    mount.append(arm_body)

    # Keyframes are width-checked against the composite's joint count, so the
    # base's `home` must grow by the arm's. Without this the model refuses to
    # compile, and dropping the keyframe instead would lose the stand pose the
    # HAL spawns from.
    base_key = base_root.find("keyframe/key")
    arm_key = arm_root.find("keyframe/key")
    if base_key is not None and arm_key is not None:
        for attr in ("qpos", "ctrl"):
            base_value, arm_value = base_key.get(attr), arm_key.get(attr)
            if base_value and arm_value:
                base_key.set(attr, f"{base_value} {arm_value}")
    elif base_key is not None:
        base_root.remove(base_root.find("keyframe"))  # type: ignore[arg-type]  # reason: guarded by base_key

    xml = ET.tostring(base_root, encoding="unicode")
    if ground:
        xml = _stage_ground(xml)
    return xml, base_path.parent / "assets"
