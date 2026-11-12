# Tasks

## 1. The fix-plan step

Kind: behavior

- [x] 1.1 Write failing tests: the selection and its bounds, the repair with the head plan as `previous` and the open findings as `problem`, the push of a better revision on the latest default branch with a lease, the label, the marks, the comment, the drain guard, the result line and the counter
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_fix_plan.py`
- [x] 1.2 Add `_Planner.revise`, `_Planner._start_item` and `revise_plan` to `src/devops_cli/roadmap/stage/stage.py`, and the step in `src/devops_cli/roadmap/steps/fix_plan.py` with the record keys, the marker, the result line and the counter
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_fix_plan.py tests/roadmap/stage/test_roadmap_stage_verification.py`

## 2. The Service row and the command

Kind: behavior

- [x] 2.1 Write failing tests: the row `fix_plan` follows `stage` in the model lane, mode `off` sends no request, mode `plan` makes no model call and no write, and `devops roadmap step fix-plan` prints the selection, runs with `--confirm` and makes no request with `--dry-run`
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_fix_plan_row.py tests/commands/test_roadmap_step_fix_plan.py`
- [x] 2.2 Add the row, the setting `roadmap.fix_plan.mode`, the group `devops roadmap step` and the command, and update the tests that list the rows of the model lane
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_fix_plan_row.py tests/commands/test_roadmap_step_fix_plan.py tests/roadmap/test_roadmap_run_due_table.py tests/roadmap/test_roadmap_run_lanes.py`

## 3. Documents

Kind: other

- [x] 3.1 Add the row `fix-plan` to ADR 0021 section 8 and ADR 0022 section 2, and update `docs/roadmap/stage.md`, `docs/ROADMAP_WORKFLOW.md`, `k8s/README.md` and `k8s/devops/configmap.example.yaml`
  - Verification: `$ uv run devops ci --check --only docs,openspec`
- [x] 3.2 Regenerate the documents of the commands, the settings and the metrics
  - Verification: `$ uv run devops docs generate --sync-readme`

- Pending a person: set `roadmap.fix_plan.mode: on` in the ConfigMap `devops-cli-config` of the Service, after a review of the selections that mode `plan` logs.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
