# Tasks

## 1. Make the review rounds a setting that extends while the open findings drop

Reads: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/service_stop.py`, `src/devops_cli/config/settings.py`. Changes: `src/devops_cli/config/constants.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_verify.py`, `src/devops_cli/roadmap/round_log.py`, `tests/roadmap/stage/test_roadmap_stage_review_rounds.py` (new), `tests/roadmap/test_roadmap_limit_classes.py`, `tests/security/test_config_declarations.py`.

- [x] 1.1 Write the tests first in `tests/roadmap/stage/test_roadmap_stage_review_rounds.py`: the setting sets the rounds, a value over the ceiling fails the settings load, a drop of the open count after the last round gives one more round and one `stage review extended:` line, a count that stays gives none, no item passes the ceiling, and no round starts after the Service stops
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_review_rounds.py`
- [x] 1.2 Add `roadmap.stage.verify_repair_rounds` with `CONST_ROADMAP_STAGE_VERIFY_REPAIR_ROUNDS_CEILING`, delete `CONST_ROADMAP_STAGE_VERIFY_REPAIR_ROUNDS`, add `repair_round_due` and `log_review_extension`, and call the drain guard before each repair round in `StageJob._verified`. Class the new limits in `tests/roadmap/test_roadmap_limit_classes.py` and declare the variable in `tests/security/test_config_declarations.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_review_rounds.py tests/roadmap/test_roadmap_limit_classes.py tests/security/test_config_declarations.py tests/roadmap/stage/test_roadmap_stage_verification.py tests/roadmap/stage/test_roadmap_stage_repair_return.py`

## 2. Documents

- [x] 2.1 State the setting, the rule of the extension and the line `stage review extended:` in `docs/roadmap/stage.md`, `docs/ROADMAP_WORKFLOW.md` and `k8s/README.md`, and regenerate the configuration documents with `devops docs generate --sync-readme`
  - Verification: `$ uv run devops ci docs`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
