# Tasks

## 1. The shadow mode

Reads: `src/devops_cli/roadmap/intake/intake_jev.py`, `src/devops_cli/roadmap/intake/intake.py`, `tests/roadmap/intake/test_roadmap_intake_jev.py`, `tests/support/fakes/jev.py`. Changes: `src/devops_cli/config/defaults.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/roadmap/intake/`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/lang/en/messages.py`.

- [x] 1.1 Write `tests/roadmap/intake/test_roadmap_intake_jev_shadow.py`: shadow changes no label and no flag, a placement records the answers, a Jev error changes nothing, agreement counts, the series count, and the setting builds a model for each mode
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [x] 1.2 Make `roadmap.intake.jev` a `JevMode`, add `ShadowIntakeModel`, `ObservingModel`, `IntakeDecision.shadow`, `IntakeRecordKey` and the counter `devops_cli_roadmap_intake_jev_shadow_total`
  - Verification: `$ uv run devops ci test tests/roadmap/intake/test_roadmap_intake_jev_shadow.py tests/roadmap/intake/test_roadmap_intake_jev.py tests/roadmap/stage/test_roadmap_stage_jev_screen.py`

## 2. The shadow report

Reads: `src/devops_cli/commands/roadmap_eval_jev.py`, `src/devops_cli/roadmap/jev_eval.py`. Changes: `src/devops_cli/commands/roadmap_eval_jev.py`, `src/devops_cli/roadmap/jev_shadow_report.py`, `src/devops_cli/lang/en/help.py`.

- [x] 2.1 Write `tests/roadmap/test_roadmap_jev_shadow_report.py` and the `--from-shadow` tests of `tests/commands/test_roadmap_eval_jev.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_jev_shadow_report.py tests/commands/test_roadmap_eval_jev.py`
- [x] 2.2 Add `jev_shadow_report.py` and the option `--from-shadow` with `--repo`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_jev_shadow_report.py tests/commands/test_roadmap_eval_jev.py`

## 3. Documents

- [x] 3.1 Update `docs/roadmap/intake.md` and the example ConfigMap, and regenerate the references
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
- Pending a person: add `intake:` / `jev: shadow` under `roadmap:` of the live ConfigMap after the new image runs.
