---
type: analysis
tags: [openral, rskill, adapters, acquire]
updated: 2026-09-19
---

# Wrapping third-party weights

OpenRAL almost never owns the neural checkpoint. An rSkill is a typed
envelope around someone else's Hub repo. "Adapt" here is **contract
remap**, not a second training run.

Related: [[entities/openral]], [[entities/acquire]],
[[analyses/creating-acquire]]. Normative packaging:
`docs/reference/rskills.md`, `docs/reference/vla_compatibility.md`,
`CLAUDE.md` rSkill + license sections.

## What the envelope is

`rskill.yaml` names the **family**, the **body**, and **where the
bytes live**. The loader (`rSkill.from_pretrained` /
`from_yaml`) validates license, tags, and capabilities. It does not
retrain.

`weights_uri` is allowed to point **off** the `OpenRAL/` org:

| Card | `weights_uri` | Upstream |
| --- | --- | --- |
| `smolvla-libero` | `hf://lerobot/smolvla_libero` | LeRobot paper ckpt |
| `rsl-rl-onnx-go2-velocity-flat` | `hf://diasAiMaster/unitree-go2-velocity-flat` | Unitree rsl-rl ONNX |
| `rskill-smolvla-so101-eraser_place-bf16` | `hf://OpenRAL/…@sha` | **mirror** of makermods; bytes identical |
| XR-1 / GR00T / OpenVLA-OFT / LingBot | pinned upstream (or sidecar) | Xiaomi, NVIDIA, RLinf, Robbyant |

A mirror exists when the catalog wants a private, SHA-pinned, inference-only
tree (no 21 GB training snapshots; no gated Hub 401). Provenance still
records `source_repo`. Weight **license** stays the upstream's
(`bsd`, π0 research, NVIDIA, RLWRLD NC, …) — OpenRAL Apache-2.0 is the
**code**, not a relicensing of the tensors.

Scaffold path: `openral rskill new <id> --from-hf <owner/repo>` reads
`config.json` and writes `model_family`, dims, camera aliases, and
`weights_uri` (`python/cli/_rskill_intel.py`).

## How a foreign ckpt actually runs

`model_family` is a closed `ModelFamily` literal. `make_policy` looks
it up in `openral_sim.registry.POLICIES`. Each family has one
`PolicyAdapter` that:

1. Resolves `weights_uri` (HF snapshot or local dir).
2. Loads with that family's native API (`SmolVLAPolicy.from_pretrained`,
   ONNX Runtime, ZMQ sidecar, …).
3. Returns a 1-D `float32` action the runner can pack into an
   `ActionChunk`.

New architecture → new adapter + methods entry. There is no generic
"load any safetensors" path.

## Three IO remaps that are not training

Same weights, different robot surface:

- **Cameras.** Robot `vla_feature_key` → VLA slot (`camera1`) →
  checkpoint key via `image_preprocessing.aliases` (`front` / `wrist`
  on the SO-101 eraser_place wrap).
- **Proprio layout.** `openral_state_adapter` assemblers rebuild the
  checkpoint's `state_contract` (LIBERO 8-D EEF, RC365, …) from live
  TF / joints. The policy never sees raw HAL order unless it trained
  on it.
- **Short action on a wider body.** `hold_pad_joint_targets` expands
  12-D Go2 legs to 19-D `go2_z1` by freezing the Z1 at episode-start
  proprio. Leading indices stay the trained joints. This is the
  on-stage **walk adopt**. Remap ≠ a 19-D policy.

## Acquire Adapt is a catalog fork, not a new brain

Sibling `edogbeatz/robo-skill-acquire` `adapt.py` (not this repo).
`/simple` first probes with `allow_adapt: false`. Embodiment reject
on walk becomes `adapt_offer`. Yes / Adapt sends `adapt: "remap"` +
`verify: true`. Hop never becomes an offer (`check=payload`).

**Is it dummy?** The button is real HTTP. The **weights are not
rewritten.** On-stage walk adopt is:

1. Acquire seed card tagged `go2` only → first probe rejects on
   `go2_z1` (even though the in-tree OpenRAL manifest already lists
   both tags — the demo needs an ask).
2. Remap forks the card (`fork/…→go2_z1`), `remapped_tags: [go2_z1]`,
   `rules_applied: [tag_family]`. Dashboard tests show
   `remapped_contracts: {}`.
3. Apply still executes the **same** 12-D ONNX
   (`execute_id_for` maps seed and fork to
   `Acquire/rskill-rsl-rl-onnx-go2-velocity-flat`).
4. What actually moves the armed twin is OpenRAL: runner
   `hold_pad_joint_targets` 12→19 + `Go2Z1MujocoHAL` sticky arm
   qpos-snap. Measured: `ready` walks, menagerie `home` tips at
   honest mass (`tests/sim/test_go2_z1_rsl_rl_onnx_mujoco.py`).

Far miss (Franka on Go2) is a hard reject — that gate is not theater.
Verify is supposed to be cricket `openral deploy sim`; this repo
does not run `adapt.py`. Unit tests use a canned FastAPI fake. Live
Railway is the sibling. Do not call Adapt a dummy click, and do not
call it a 19-D policy.

**Remap does not retune the gait.** Sibling `adapt.py` can rewrite
IO tables on other families (camera aliases, joint order, gripper
scale). This pair applies `tag_family` only. It does not patch
`action_scale`, `default_joint_pos`, observation dim, PD gains, or
`velocity_commands`. Those live in Hub `deploy.yaml` / the HAL /
`goal_params_json`, and the ONNX was trained on a **bare** 12-DoF
dog. Changing CoM / `arm_mass_scale` / pitch inertia does not make
the same net a payload policy
([[analyses/go2-z1-arm-pose-decides-the-walk]]). `/simple` chat names
a live tip as **the unit fell. this skill needs retraining or
finetuning.** — verify miss, not this remap. A payload-aware walk is
**mjlab resume**, then a new card — not this remap
([[analyses/go2-z1-payload-walk-finetune]]).

## Quantization is packing, not wrapping

Quantization is how a datacentre bf16/fp32 VLA is stored and run in
fewer bits so it fits an 8 GB card. It is **not** remap, hold-pad, or
a new policy. Normative: `docs/tutorials/rskill/quantize-an-rskill.md`.

| Token | vs bf16 | What it is |
| --- | --- | --- |
| `bf16` / `fp32` | baseline | storage + compute; no Linear rewrite |
| `int8` | ~50% | bitsandbytes LLM.int8 (`Linear8bitLt`); on-line only |
| `nf4` / `int4` | ~25% | bitsandbytes NF4 (`Linear4bit`); on-line or prequant pack |

Only Linears with ≥4M weight elements are rewritten. Small heads stay
in the compute dtype. `Skill.configure` always calls `on_quantize`;
the default is a no-op. Packing happens when
`resolve_quant_plan` yields `nf4`/`int8`
(`$OPENRAL_QUANTIZATION_DTYPE` > `spec.extra.dtype` > manifest >
adapter default). Override vs declared dtype logs **WARNING** — never
silent. ONNX Runtime refuses post-load quantize; it must be
pre-applied at export.

Two NF4 paths, same accuracy: on-line rewrite every launch (~90 s on
a 4070-mobile) vs `tools/quantize_rskill.py` writing
`quantization_metadata.json` + packed `model.safetensors` (warm load
~10 s). GR00T/RLDX cards are often *named* bf16 while the adapter
NF4-packs on load (`manifest_dtype_is_storage`). π0.5 / MolmoAct2
declare the runtime dtype.

Acquire beachhead did **not** quantize: walk is fp32 ONNX, Z1 is
scripted fp32, SO-101 eraser_place is a bf16 wrap. In-tree NF4 cards
(MolmoAct2, Robometer, LocateAnything, …) are a different slice.

## What this is not

- Not a training farm. Isaac Lab trains `rsl_rl_onnx`; OpenRAL
  wraps the export.
- Not auto-quantize on every load. `on_quantize` is a no-op unless
  the manifest / env asks.
- Not relicensing. Loader guards (`OPENRAL_ALLOW_NONCOMMERCIAL`,
  pickle, `trust_remote_code`) stay on.
