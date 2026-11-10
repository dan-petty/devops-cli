# Tasks

## 1. Shared parts and the screen

Reads: `src/devops_cli/ai/jev.py`, `src/devops_cli/roadmap/stage/stage_verify.py`, `src/devops_cli/roadmap/stage/stage.py`, `docs/adr/0019-a-decision-step-asks-jev-short-closed-questions-about-evidence-that-tools-extract.md`. Changes: `src/devops_cli/roadmap/decision_step.py` (new), `src/devops_cli/roadmap/decision_fit.py` (new), `src/devops_cli/roadmap/stage/stage_jev_screen.py` (new), `src/devops_cli/roadmap/stage/stage.py`.

- [x] 1.1 Write failing tests for the bands, the fit, the halves, the digest, the three modes and the fail-open rule, with the Jev edge fake
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_decision_step.py tests/roadmap/test_roadmap_decision_fit.py tests/roadmap/stage/test_roadmap_stage_jev_screen.py`
- [x] 1.2 Add the shared module, the fit, the screen, the setting `roadmap.stage.jev_screen`, the two counters and the call site in the stage review
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_jev_screen.py`

## 2. The eval command and the cuts

Reads: `src/devops_cli/commands/roadmap_eval_verify.py`, `src/devops_cli/roadmap/stage/stage_verify_eval.py`. Changes: `src/devops_cli/roadmap/stage/stage_screen_eval.py` (new), `src/devops_cli/commands/roadmap_eval_screen.py` (new), `tests/fixtures/roadmap_eval/stage/split.json` (new), `src/devops_cli/roadmap/stage/jev_screen_cuts.json` (new).

- [x] 2.1 Write failing tests for the cascade score, the oracle, the report and the dry run
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_screen_eval.py tests/commands/test_roadmap_eval_screen.py`
- [x] 2.2 Add the score, the command, the fixed split and the fitted cuts from a live run
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_eval_screen.py`

## 3. Documents

- [x] 3.1 Document the setting, the counters and the command, and add the example key to the ConfigMap example
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Pilot 2 of ADR 0019, the failure-class tail, is planned in the record and waits for a person to file it.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
