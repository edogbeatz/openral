"""Sibling Acquire HTTP surface for dashboard tests.

Returns the presentation trio (walk fit / walk embodiment reject /
hop payload reject / remap fork). Chat must talk HTTP — do not stub
``probe()``.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

WALK_SEED = "seed/rskill-rsl-rl-onnx-go2-velocity-flat"
HOP_SEED = "seed/rskill-rsl-rl-onnx-go2-hop-flat"
WALK_FORK = f"fork/{WALK_SEED}→go2_z1"


def fake_acquire_app() -> FastAPI:
    """ASGI app that records ``POST /v1/skills/acquire`` bodies."""
    app = FastAPI()
    app.state.calls: list[dict[str, Any]] = []

    @app.post("/v1/skills/acquire")
    async def acquire(request: Request) -> JSONResponse:
        body = await request.json()
        if not isinstance(body, dict):
            return JSONResponse({"error": "invalid json"}, status_code=400)
        app.state.calls.append(dict(body))
        skill_id = str(body.get("skill_id") or "")
        embodiment = str(body.get("embodiment") or "")
        adapt = body.get("adapt")
        if skill_id == WALK_SEED and embodiment == "go2":
            payload = _fit(skill_id, body)
        elif skill_id == WALK_SEED and embodiment == "go2_z1" and adapt == "remap":
            payload = _adapted(body)
        elif skill_id == WALK_SEED and embodiment == "go2_z1":
            payload = _embodiment_reject(skill_id, body)
        elif skill_id == HOP_SEED and embodiment == "go2":
            payload = _fit(skill_id, body)
        elif skill_id == HOP_SEED and embodiment == "go2_z1":
            payload = _payload_reject(skill_id, body)
        else:
            return JSONResponse({"error": "unknown card"}, status_code=404)
        return JSONResponse(payload)

    return app


def _base(body: dict[str, Any], skill_id: str) -> dict[str, Any]:
    return {
        "job_id": "job-test",
        "session_id": str(body.get("session_id") or ""),
        "skill_id": skill_id,
        "promoted": False,
        "skipped": False,
        "ranker": None,
    }


def _fit(skill_id: str, body: dict[str, Any]) -> dict[str, Any]:
    out = _base(body, skill_id)
    out.update(
        {
            "status": "pending" if body.get("verify") is False else "verified",
            "adapted": False,
            "mismatch_report": None,
            "adapt_report": None,
            "parent_skill_id": None,
            "promoted": body.get("verify") is not False,
        }
    )
    return out


def _embodiment_reject(skill_id: str, body: dict[str, Any]) -> dict[str, Any]:
    out = _base(body, skill_id)
    out.update(
        {
            "status": "rejected",
            "adapted": False,
            "mismatch_report": {
                "ok": False,
                "reasons": [
                    {
                        "check": "embodiment",
                        "message": "card tagged go2; occupant is go2_z1",
                        "detail": {},
                    }
                ],
            },
            "adapt_report": None,
            "parent_skill_id": None,
        }
    )
    return out


def _payload_reject(skill_id: str, body: dict[str, Any]) -> dict[str, Any]:
    out = _base(body, skill_id)
    out.update(
        {
            "status": "rejected",
            "adapted": False,
            "mismatch_report": {
                "ok": False,
                "reasons": [
                    {
                        "check": "payload",
                        "message": "unladen hop; 4.69 kg arm on the head",
                        "detail": {"payload_kg": 4.69, "payload_limit_kg": 0.0},
                    }
                ],
            },
            "adapt_report": None,
            "parent_skill_id": None,
        }
    )
    return out


def _adapted(body: dict[str, Any]) -> dict[str, Any]:
    out = _base(body, WALK_FORK)
    out.update(
        {
            "status": "verified",
            "adapted": True,
            "promoted": True,
            "parent_skill_id": WALK_SEED,
            "mismatch_report": {
                "ok": False,
                "reasons": [
                    {
                        "check": "embodiment",
                        "message": "card tagged go2; occupant is go2_z1",
                        "detail": {},
                    }
                ],
            },
            "adapt_report": {
                "ok": True,
                "parent_id": WALK_SEED,
                "fork_id": WALK_FORK,
                "family": ["go2", "go2_z1"],
                "remapped_tags": ["go2_z1"],
                "remapped_contracts": {},
                "rules_applied": ["tag_family"],
                "reason": "near_morphology_tag_family",
                "detail": {},
            },
        }
    )
    return out
