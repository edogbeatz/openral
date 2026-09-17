"""Expose ``package://`` URDF meshes to Foxglove's web client.

``robot_descriptions`` URDFs (Go2, many others) stamp meshes as
``package://<name>/…``. That name is not an ament package on the ROS path,
so the bridge's ``assets`` fetch fails and Studio's 3D panel draws TF axes
only. Foxglove Studio — browser and desktop — only *requests* ``package://``
from the bridge (``file://`` is read off the machine running Studio). The
fix is to leave the URDF on ``package://`` and register each resolvable
package in a throwaway ament prefix the bridge process can see. No closed
meshes are vendored.
"""

from __future__ import annotations

import os
import re
import shutil
from collections.abc import Mapping
from pathlib import Path

#: ``filename="package://pkg/rel/path.ext"`` (single or double quotes).
_PACKAGE_MESH_RE = re.compile(r"""(filename=["'])package://([^/"']+)/([^"']+)(["'])""")

#: Package names written under the overlay share dir — no path separators.
_PKG_NAME_RE = re.compile(r"^[-\w%.]+$")

#: Default overlay prefix used by deploy-sim / ``foxglove.launch.py``.
DEFAULT_OVERLAY_ROOT = Path("/tmp/openral_foxglove_ament")


def discover_package_mesh_roots(xml: str, *, urdf_path: Path) -> dict[str, Path]:
    """Map each resolvable ``package://`` package to its on-disk share.

    Unresolvable refs (missing file, path escape, no parent dir named after
    the package) are omitted so a real ament package on the ROS path keeps
    working without an overlay entry.

    Args:
        xml: URDF document text.
        urdf_path: Path of the URDF on disk. Walked upward to find a
            directory named after the ``package://`` package.

    Returns:
        ``{package_name: share_dir}`` for every package that has at least
        one mesh file under the URDF's package tree.

    Example:
        >>> from pathlib import Path
        >>> import tempfile
        >>> root = Path(tempfile.mkdtemp())
        >>> pkg = root / "go2_description"
        >>> (pkg / "meshes").mkdir(parents=True)
        >>> _ = (pkg / "meshes" / "base.dae").write_bytes(b"<asset/>")
        >>> urdf = pkg / "urdf" / "go2.urdf"
        >>> urdf.parent.mkdir()
        >>> body = (
        ...     '<robot name="go2">'
        ...     '<mesh filename="package://go2_description/meshes/base.dae"/>'
        ...     "</robot>"
        ... )
        >>> found = discover_package_mesh_roots(body, urdf_path=urdf)
        >>> list(found) == ["go2_description"]
        True
        >>> found["go2_description"] == pkg.resolve()
        True
    """
    resolved_urdf = Path(urdf_path).resolve()
    found: dict[str, Path] = {}
    for match in _PACKAGE_MESH_RE.finditer(xml):
        pkg, rel = match.group(2, 3)
        if pkg in found:
            continue
        path = _resolve_package_file(pkg, rel, resolved_urdf)
        if path is None:
            continue
        share = _package_share(pkg, resolved_urdf)
        if share is None:
            continue
        found[pkg] = share
    return found


def install_ament_mesh_overlay(
    packages: Mapping[str, Path], *, overlay_root: Path
) -> Path:
    """Write an ament prefix that exposes each package via the resource index.

    ``<overlay>/share/<pkg>`` is a symlink to the on-disk share. The index
    marker ``<overlay>/share/ament_index/resource_index/packages/<pkg>`` is
    what ``get_package_share_directory`` looks up. Rebuilds ``share/`` on
    each call so a restarted deploy does not accumulate stale links.

    Args:
        packages: ``{package_name: share_dir}`` from
            :func:`discover_package_mesh_roots`.
        overlay_root: Directory that becomes one ``AMENT_PREFIX_PATH`` entry.

    Returns:
        ``overlay_root`` resolved.

    Example:
        >>> from pathlib import Path
        >>> import tempfile
        >>> src = Path(tempfile.mkdtemp()) / "go2_description"
        >>> (src / "meshes").mkdir(parents=True)
        >>> _ = (src / "meshes" / "base.dae").write_bytes(b"<asset/>")
        >>> overlay = Path(tempfile.mkdtemp()) / "overlay"
        >>> root = install_ament_mesh_overlay({"go2_description": src}, overlay_root=overlay)
        >>> (root / "share" / "go2_description" / "meshes" / "base.dae").is_file()
        True
        >>> (root / "share" / "ament_index" / "resource_index" / "packages" / "go2_description").is_file()
        True
    """
    root = Path(overlay_root).resolve()
    share = root / "share"
    if share.exists():
        shutil.rmtree(share)
    index = share / "ament_index" / "resource_index" / "packages"
    index.mkdir(parents=True)
    for pkg, src in packages.items():
        if not _PKG_NAME_RE.fullmatch(pkg):
            continue
        dest = share / pkg
        dest.symlink_to(Path(src).resolve(), target_is_directory=True)
        (index / pkg).write_text("")
    return root


def ament_prefix_with_overlay(overlay_root: Path, *, existing: str | None = None) -> str:
    """Prepend ``overlay_root`` to ``AMENT_PREFIX_PATH`` without dropping ROS.

    ``launch_ros.actions.Node(additional_env=…)`` *replaces* the named
    variable, so the caller must pass the composed value — otherwise the
    bridge cannot find ``foxglove_bridge`` itself.

    Args:
        overlay_root: Prefix produced by :func:`install_ament_mesh_overlay`.
        existing: Value to prepend to. ``None`` reads the process environment.

    Returns:
        Colon-separated prefix list.

    Example:
        >>> from pathlib import Path
        >>> overlay = Path("/opt/overlay")
        >>> ament_prefix_with_overlay(overlay, existing="/opt/ros/jazzy") == (
        ...     f"{overlay.resolve()}:/opt/ros/jazzy"
        ... )
        True
        >>> ament_prefix_with_overlay(
        ...     overlay, existing=f"{overlay.resolve()}:/opt/ros/jazzy"
        ... ) == f"{overlay.resolve()}:/opt/ros/jazzy"
        True
    """
    prefix = str(Path(overlay_root).resolve())
    current = os.environ.get("AMENT_PREFIX_PATH", "") if existing is None else existing
    if not current:
        return prefix
    parts = current.split(":")
    if prefix in parts:
        return current
    return f"{prefix}:{current}"


def prepare_foxglove_mesh_overlay(
    xml: str, *, urdf_path: Path, overlay_root: Path = DEFAULT_OVERLAY_ROOT
) -> tuple[dict[str, str], tuple[str, ...]]:
    """Install the overlay and return the env the Foxglove bridge process needs.

    Leaves ``xml`` unchanged — Studio's web client only asks the bridge for
    ``package://`` URIs.

    Args:
        xml: URDF document text (not rewritten).
        urdf_path: Path of the URDF on disk.
        overlay_root: Directory that becomes one ``AMENT_PREFIX_PATH`` entry.

    Returns:
        ``(additional_env, package_names)``. ``additional_env`` is empty
        when nothing was resolvable.

    Example:
        >>> from pathlib import Path
        >>> import tempfile
        >>> pkg = Path(tempfile.mkdtemp()) / "go2_description"
        >>> (pkg / "meshes").mkdir(parents=True)
        >>> _ = (pkg / "meshes" / "base.dae").write_bytes(b"<asset/>")
        >>> urdf = pkg / "urdf" / "go2.urdf"
        >>> urdf.parent.mkdir()
        >>> body = (
        ...     '<robot name="go2">'
        ...     '<mesh filename="package://go2_description/meshes/base.dae"/>'
        ...     "</robot>"
        ... )
        >>> overlay = Path(tempfile.mkdtemp()) / "overlay"
        >>> env, names = prepare_foxglove_mesh_overlay(
        ...     body, urdf_path=urdf, overlay_root=overlay
        ... )
        >>> names
        ('go2_description',)
        >>> "AMENT_PREFIX_PATH" in env
        True
        >>> "package://go2_description" in body
        True
    """
    packages = discover_package_mesh_roots(xml, urdf_path=urdf_path)
    if not packages:
        return {}, ()
    overlay = install_ament_mesh_overlay(packages, overlay_root=overlay_root)
    return (
        {"AMENT_PREFIX_PATH": ament_prefix_with_overlay(overlay)},
        tuple(sorted(packages)),
    )


def _resolve_package_file(pkg: str, rel: str, urdf_path: Path) -> Path | None:
    """Resolve ``package://pkg/rel`` against a parent directory named ``pkg``."""
    share = _package_share(pkg, urdf_path)
    if share is None:
        return None
    candidate = (share / rel).resolve()
    if not candidate.is_file():
        return None
    if not _is_under(candidate, share):
        return None
    return candidate


def _package_share(pkg: str, urdf_path: Path) -> Path | None:
    """The on-disk directory named ``pkg`` that contains ``urdf_path``."""
    for parent in (urdf_path.parent, *urdf_path.parents):
        if parent.name == pkg:
            return parent
    return None


def _is_under(path: Path, root: Path) -> bool:
    """True when ``path`` is ``root`` or a descendant (no ``..`` escape)."""
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True
