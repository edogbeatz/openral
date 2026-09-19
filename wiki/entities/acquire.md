---
type: entity
tags: [openral, acquire, product]
updated: 2026-09-19
linear: [1-189, 1-225]
---

# Acquire

Install-on-the-fly rSkill acquisition that sits **on top of** OpenRAL, not
inside it. Sibling repo `edogbeatz/robo-skill-acquire` (Linear project
**Acquire**, team LaunchPad). This workspace (`edogbeatz/openral`) is the
fork Acquire pins for Go2 verify.

**Loop:** retrieve → reject → install → adapt? → verify → promote → run.
**Rule:** reject is free · adapt is the product · verify is the warranty.

On-stage catalog: walk **fits** bare Go2; walk **adopts** onto Go2+Z1;
unladen hop **rejects** on the armed twin (payload 4.69 kg). Lives in
the sibling seed DB. `/simple` chat is the landed probe/ask wire
(`POST /api/chat` → `POST /v1/skills/acquire`, `allow_adapt: false`
first, ask before remap). Switching UNIT chats **unit changed.** only
when the occupant actually changes (not reselect, not first Load).
Chat maps **go left** / **left** / **walk left** onto walk
`turn_left` (yaw joystick) in `parse_intent` before Acquire sees the
task — that is not a Jev reasoner turn. A live tip past 1.0 rad chats
**the unit fell. this skill needs retraining or finetuning.** once
until RESET — that is verify miss, not Adapt (remap does not retune).
The dashboard that serves `/simple` must
have `ACQUIRE_API_URL` + `ACQUIRE_API_KEY` at process start. Seed
once with `just dashboard-acquire-env` (`~/.openral/dashboard.env`);
`openral dashboard` loads that file into empty `ACQUIRE_API_*`.
Empty URL is FAULT, not a Jev miss.
Reasoner `AcquireSkillTool` is still a
separate follow-up.
**Not:** a better harness, a training farm, or a marketplace (storefront
is phase 2).

Hero user is the **agent**. Success is a task unblocked this session
without a human `openral rskill install` mid-flight.

OpenRAL already searches the Hub and refuses a wrong body. That is the
runtime. Acquire is the layer that ranks, remaps a near miss, and keeps
the card only after verify. Same words in this repo (search, near-miss,
reject) are Hub text, collision probes, and `check_capabilities` —
not this loop. Jev/TypeSafe ranks the catalog and can pick a near parent after the
family table (sibling, opt-in `ACQUIRE_TYPESAFE=1`). It must not
replace the hard gate, remap, or verify. See [[analyses/creating-acquire]].

Canonical synthesis: [[analyses/creating-acquire]]. How foreign
checkpoints become runnable without retraining:
[[analyses/wrapping-third-party-weights]]. `/simple` walk **Adapt**
on Go2+Z1 is tag-fork + hold-pad, not a payload policy; finetune is
mjlab resume then a new card:
[[analyses/go2-z1-payload-walk-finetune]]. OpenRAL substrate:
[[entities/openral]]. Beachhead robot: [[entities/go2]]. Isaac Lab
posture for the MVP: [[analyses/isaac-lab-with-openral]].
