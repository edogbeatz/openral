#!/usr/bin/env bash
# Canonical ``mypy --strict`` surface. Justfile ``lint``, quality.yml,
# release-pypi.yml, and the pre-commit hook all call this so the package list
# cannot drift across those four sites.
#
# Covered: openral_core, openral_cli, openral_sim, openral_observability,
# openral_runner, openral_reasoner, openral_wam, openral_hal, plus tools/.
#
# Not in this set (follow-up unless a first ``mypy --strict -p`` pass is
# already clean): openral_dataset, openral_detect, openral_rskill,
# openral_sensors, openral_state_adapter, openral_world_state.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

uv run mypy --strict \
  -p openral_core \
  -p openral_cli \
  -p openral_sim \
  -p openral_observability \
  -p openral_runner \
  -p openral_reasoner \
  -p openral_wam \
  -p openral_hal
uv run mypy --strict tools/
