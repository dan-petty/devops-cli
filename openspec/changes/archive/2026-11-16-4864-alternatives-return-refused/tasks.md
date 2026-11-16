# Tasks: #4864

## 1. Decision point and cuts file

Reads: `src/devops_cli/roadmap/decision_point.py`, `src/devops_cli/roadmap/decision_table.py`. Changes: `src/devops_cli/roadmap/alternatives_cuts.json` (new), `src/devops_cli/roadmap/alternatives_reply_fixable.py` (new), `src/devops_cli/roadmap/decision_registry.py`, `src/devops_cli/roadmap/decision_table.py`.

- [x] 1.1 Create `src/devops_cli/roadmap/alternatives_cuts.json` with fixable codes table.
  - Verification: `$ uv run python -c "from devops_cli.roadmap.decision_step import Thresholds; from pathlib import Path; Thresholds.load(Path('src/devops_cli/roadmap/alternatives_cuts.json'))"`
- [x] 1.2 Implement `alternatives_reply_fixable.py` with `REPLY_FIXABLE` decision point.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_decision_table.py`
- [x] 1.3 Register `REPLY_FIXABLE` in `decision_registry.py` and `decision_table.py`.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_decision_table.py`

## 2. Store keys, refusal classification, returns, and result lines

Reads: `src/devops_cli/roadmap/alternatives_reply_fixable.py`, `src/devops_cli/roadmap/job_result.py`. Changes: `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/alternatives.py`.

- [x] 2.1 Add `AlternativesRecordKey.FAILED_REASON` and update `settle` to record and clear it.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_alternatives_job_result.py`
- [x] 2.2 Map refusal reasons to stable codes and record them in `CheckFailure`.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_alternatives_job_result.py`
- [x] 2.3 Wire `alternatives.reply_fixable` decision point into `_check_one` output validation and return once in mode `on`.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_alternatives_job_result.py`
- [x] 2.4 Update result line logging in `_log` to include refusal reason code and decision band.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_alternatives_job_result.py`

## 3. Tests and specification updates

Reads: `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/alternatives_reply_fixable.py`. Changes: `tests/config/test_decision_point_settings.py`, `tests/roadmap/test_roadmap_alternatives_job_result.py`, `tests/roadmap/test_roadmap_alternatives_reply_fixable.py` (new), `openspec/specs/roadmap-alternatives/spec.md`.

- [x] 3.1 Update registry counts and names in `test_decision_point_settings.py`.
  - Verification: `$ uv run devops ci test tests/config/test_decision_point_settings.py`
- [x] 3.2 Update `test_roadmap_alternatives_job_result.py` to assert reason code.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_alternatives_job_result.py`
- [x] 3.3 Add comprehensive unit tests in `test_roadmap_alternatives_reply_fixable.py`.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_alternatives_reply_fixable.py`
- [x] 3.4 Append new requirements to `openspec/specs/roadmap-alternatives/spec.md`.
  - Verification: `$ uv run devops openspec check`

## Criteria

- Group 1: Decision point `alternatives.reply_fixable` loads cuts and registers in `POINT_CUTS` and `REGISTRY`.
- Group 2: Fixable refusal returns once in mode `on`, records stable reason codes and decision bands, and clears `failed_reason` on success.
- Group 3: Tests pass and verify repeated reason stops, shadow mode records band without return, and budget limits hold.
