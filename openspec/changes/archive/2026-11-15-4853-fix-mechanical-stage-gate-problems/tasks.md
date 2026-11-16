# Tasks

## 1. Mechanical Rewrite Engine

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_findings.py`, `src/devops_cli/roadmap/stage/stage_finding_classes.json`. Changes: `src/devops_cli/roadmap/stage/stage_rewrite.py`, `tests/roadmap/stage/test_roadmap_stage_mechanical_rewrite.py`.

- [x] 1.1 Add unit tests for mechanical finding rewrites
  - Verification: `$ uv run pytest tests/roadmap/stage/test_roadmap_stage_mechanical_rewrite.py`
- [x] 1.2 Implement `apply_mechanical_rewrites` for mechanical codes
  - Verification: `$ uv run pytest tests/roadmap/stage/test_roadmap_stage_mechanical_rewrite.py`

## 2. Findings Classification and Telemetry

Kind: behavior. Reads: `src/devops_cli/telemetry/instruments.py`. Changes: `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/roadmap/stage/stage_findings.py`, `src/devops_cli/roadmap/stage/stage_finding_classes.json`, `docs/TELEMETRY.md`.

- [x] 2.1 Add `ROADMAP_FIX_CHECKS_TOTAL` instrument and classify registry as mechanical
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_findings.py`
- [x] 2.2 Regenerate telemetry documentation
  - Verification: `$ uv run devops ci docs`

## 3. Stage Loop Integration

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage.py`. Changes: `src/devops_cli/roadmap/stage/stage.py`.

- [x] 3.1 Integrate mechanical rewrite in `_returned` with a two-pass bound
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_mechanical_rewrite.py`
