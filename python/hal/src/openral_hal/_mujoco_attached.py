"""Resolve ``AttachedCollisionObject`` snapshots onto live MuJoCo bodies.

Shared by ``SimAttachedHAL`` (scene-attached rollouts) and ``MujocoArmHAL``
(bare digital twins). Both expose ``update_attached_objects`` so
``SimSensorBridge`` can heartbeat ``/openral/attachment_state`` — without
that producer the safety kernel's attached-collision gate fail-closes every
``JOINT_POSITION`` chunk after the empty-seed deadline
(``attached_unavailable``).
"""

from __future__ import annotations

from typing import Any

from openral_core import AttachedCollisionObject
from openral_core.exceptions import ROSConfigError

__all__ = ["resolve_attached_mujoco_bodies"]


def resolve_attached_mujoco_bodies(
    objects: list[AttachedCollisionObject],
    *,
    handles: tuple[Any, Any] | None,
) -> tuple[dict[str, AttachedCollisionObject], frozenset[int]]:
    """Validate an attachment set and map ``mujoco_body:`` refs to body ids.

    Args:
        objects: Complete current attachment set (empty = nothing carried).
        handles: Live ``(MjModel, MjData)`` or ``None`` before connect.

    Returns:
        ``(by_object_id, body_ids)`` including descendant bodies of each root.

    Raises:
        ROSConfigError: Duplicate ids, non-empty set without handles, malformed
            ``evidence_ref``, or unknown body name.
    """
    by_id = {obj.object_id: obj for obj in objects}
    if len(by_id) != len(objects):
        raise ROSConfigError("Attached collision object ids must be unique.")
    if handles is None:
        if objects:
            raise ROSConfigError(
                "Attached collision body masking requires MuJoCo handles."
            )
        return {}, frozenset()

    import mujoco  # noqa: PLC0415  # reason: optional sim dependency guarded by handles

    model, _data = handles
    roots: set[int] = set()
    for obj in objects:
        prefix = "mujoco_body:"
        if obj.evidence_ref is None or not obj.evidence_ref.startswith(prefix):
            raise ROSConfigError(
                f"Attached object {obj.object_id!r} requires "
                "evidence_ref='mujoco_body:<body-name>' in deploy sim."
            )
        body_name = obj.evidence_ref.removeprefix(prefix)
        body_id = int(mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, body_name))
        if body_id < 0:
            raise ROSConfigError(
                f"Attached object {obj.object_id!r} references unknown "
                f"MuJoCo body {body_name!r}."
            )
        roots.add(body_id)

    body_ids = set(roots)
    for body_id in range(1, int(model.nbody)):
        if int(model.body_parentid[body_id]) in body_ids:
            body_ids.add(body_id)
    return by_id, frozenset(body_ids)
