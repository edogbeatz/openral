"""Guards for the Foxglove ament mesh overlay — the web client fetches package://.

Uses a real on-disk package tree (not a mock). When ``robot_descriptions``
has cached ``go2_description``, the live Unitree URDF is registered too.
"""

from __future__ import annotations

import doctest
import importlib.util
import re
from pathlib import Path
from types import ModuleType

import pytest

_PKG_DIR = Path(__file__).resolve().parent.parent


def _load(name: str, filename: str) -> ModuleType:
    """Load a package module by path (ament package, not pip-installed)."""
    spec = importlib.util.spec_from_file_location(
        name, _PKG_DIR / "openral_foxglove_bringup" / filename
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_mesh = _load("_fxbringup_mesh_uris", "mesh_uris.py")
_topics = _load("_fxbringup_topics_mesh", "topics.py")

discover_package_mesh_roots = _mesh.discover_package_mesh_roots
install_ament_mesh_overlay = _mesh.install_ament_mesh_overlay
ament_prefix_with_overlay = _mesh.ament_prefix_with_overlay
prepare_foxglove_mesh_overlay = _mesh.prepare_foxglove_mesh_overlay
ASSET_URI_ALLOWLIST: list[str] = _topics.ASSET_URI_ALLOWLIST


def _is_allowed(uri: str) -> bool:
    """Whether the bridge's asset allowlist matches ``uri`` (``std::regex_match``)."""
    return any(re.fullmatch(pat, uri) for pat in ASSET_URI_ALLOWLIST)


def _go2_tree(tmp_path: Path) -> tuple[Path, Path, str]:
    """A minimal ``go2_description`` tree + URDF body next to a mesh."""
    pkg = tmp_path / "go2_description"
    mesh = pkg / "meshes" / "base.dae"
    mesh.parent.mkdir(parents=True)
    mesh.write_bytes(b"<asset/>")
    urdf = pkg / "urdf" / "go2.urdf"
    urdf.parent.mkdir()
    xml = (
        '<robot name="go2">'
        '<mesh filename="package://go2_description/meshes/base.dae"/>'
        "</robot>"
    )
    return pkg, urdf, xml


def test_discover_resolves_package_next_to_urdf(tmp_path: Path) -> None:
    """A package-tree next to the URDF is the share the overlay will expose."""
    pkg, urdf, xml = _go2_tree(tmp_path)
    found = discover_package_mesh_roots(xml, urdf_path=urdf)
    assert found == {"go2_description": pkg.resolve()}


def test_prepare_leaves_package_uri_and_registers_ament_index(tmp_path: Path) -> None:
    """Studio's web client only requests package:// — the URDF must keep it."""
    pkg, urdf, xml = _go2_tree(tmp_path)
    overlay = tmp_path / "overlay"
    env, names = prepare_foxglove_mesh_overlay(xml, urdf_path=urdf, overlay_root=overlay)
    assert names == ("go2_description",)
    assert "package://go2_description/meshes/base.dae" in xml
    assert "file://" not in xml
    linked = overlay / "share" / "go2_description" / "meshes" / "base.dae"
    assert linked.is_file()
    assert linked.resolve() == (pkg / "meshes" / "base.dae").resolve()
    marker = overlay / "share" / "ament_index" / "resource_index" / "packages" / "go2_description"
    assert marker.is_file()
    assert env["AMENT_PREFIX_PATH"].split(":")[0] == str(overlay.resolve())


def test_leaves_unresolved_package_out_of_the_overlay(tmp_path: Path) -> None:
    """A package:// that is not on disk is not registered (ament may still serve it)."""
    urdf = tmp_path / "orphan.urdf"
    urdf.write_text("<robot/>")
    xml = '<mesh filename="package://openarm_description/assets/arm.dae"/>'
    found = discover_package_mesh_roots(xml, urdf_path=urdf)
    assert found == {}
    env, names = prepare_foxglove_mesh_overlay(xml, urdf_path=urdf, overlay_root=tmp_path / "o")
    assert env == {}
    assert names == ()


def test_refuses_path_escape(tmp_path: Path) -> None:
    """``package://pkg/../outside.dae`` must not register the package from that ref."""
    pkg = tmp_path / "go2_description"
    pkg.mkdir()
    outside = tmp_path / "secret.dae"
    outside.write_bytes(b"nope")
    urdf = pkg / "robot.urdf"
    urdf.write_text("<robot/>")
    xml = '<mesh filename="package://go2_description/../secret.dae"/>'
    assert discover_package_mesh_roots(xml, urdf_path=urdf) == {}


def test_file_allowlist_rejects_traversal() -> None:
    """The file:// allowlist is the only thing between a viewer and the host fs."""
    assert not _is_allowed("file:///tmp/../etc/passwd")
    assert not _is_allowed("file:///etc/passwd")
    assert _is_allowed("file:///home/ubuntu/.cache/robot_descriptions/go2/meshes/base.dae")
    assert _is_allowed("package://go2_description/meshes/base.dae")


def test_prefix_does_not_drop_the_existing_ros_path() -> None:
    """Replacing AMENT_PREFIX_PATH wholesale would hide foxglove_bridge itself."""
    overlay = Path("/opt/overlay")
    composed = ament_prefix_with_overlay(overlay, existing="/opt/ros/jazzy:/ws/install")
    assert composed.startswith(f"{overlay.resolve()}:")
    assert "/opt/ros/jazzy" in composed.split(":")
    assert ament_prefix_with_overlay(overlay, existing=composed) == composed


def test_prepare_prepends_process_ament_prefix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The env handed to the bridge keeps the process ROS prefix."""
    _, urdf, xml = _go2_tree(tmp_path)
    monkeypatch.setenv("AMENT_PREFIX_PATH", "/opt/ros/jazzy")
    env, _names = prepare_foxglove_mesh_overlay(
        xml, urdf_path=urdf, overlay_root=tmp_path / "overlay"
    )
    parts = env["AMENT_PREFIX_PATH"].split(":")
    assert parts[0] == str((tmp_path / "overlay").resolve())
    assert "/opt/ros/jazzy" in parts


def test_go2_robot_descriptions_urdf_registers_existing_files(tmp_path: Path) -> None:
    """The live Go2 URDF's meshes become package:// the overlay can serve."""
    try:
        import robot_descriptions.go2_description as go2
    except Exception as exc:  # cache clone / git fetch can fail offline
        pytest.skip(f"robot_descriptions.go2_description unavailable: {exc}")
    urdf_path = Path(go2.URDF_PATH)
    if not urdf_path.is_file():
        pytest.skip(f"go2_description.URDF_PATH missing: {urdf_path}")
    xml = urdf_path.read_text(encoding="utf-8")
    if "package://go2_description" not in xml:
        pytest.skip("go2 URDF has no package://go2_description mesh refs")
    env, names = prepare_foxglove_mesh_overlay(
        xml, urdf_path=urdf_path, overlay_root=tmp_path / "overlay"
    )
    assert names == ("go2_description",)
    assert "package://go2_description" in xml
    assert "file://go2_description" not in xml
    assert env["AMENT_PREFIX_PATH"].split(":")[0] == str((tmp_path / "overlay").resolve())
    share = tmp_path / "overlay" / "share" / "go2_description"
    uris = re.findall(r'filename="package://go2_description/([^"]+)"', xml)
    assert uris, "expected at least one go2_description mesh ref"
    for rel in uris:
        path = share / rel
        assert path.is_file(), f"overlay does not expose {rel}: {path}"


def test_mesh_uris_module_docstring_examples_run() -> None:
    """Every ``Example`` in the module's docstrings executes (CLAUDE.md §2)."""
    results = doctest.testmod(_mesh, verbose=False)
    assert results.failed == 0, f"{results.failed} doctest failure(s) in mesh_uris.py"
