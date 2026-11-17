# Tasks

## 1. Take the files that the change causes into the repair scope

Kind: behavior. Changes: `src/devops_cli/roadmap/steps/fix_checks_cause.py` (new), `src/devops_cli/roadmap/steps/fix_checks.py`, `src/devops_cli/roadmap/steps/fix_checks_repair.py`, `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/steps/test_fix_checks_cause.py` (new), `tests/roadmap/steps/test_roadmap_step_fix_checks.py`, `tests/roadmap/steps/test_roadmap_step_fix_checks_repair.py`.

- [x] 1.1 Write the failing cases from the text of #6114: a test that calls the changed `_run_pr_review_workflow` is in scope with its file named; a test of a changed module is in scope; a file that main changed after the branch point stops as main skew; a file that the change does not cause, and a log that names no file of the checkout, stop with a reason that names them; a round gives the files to the model, and its comment names them
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_fix_checks_cause.py tests/roadmap/steps/test_roadmap_step_fix_checks.py tests/roadmap/steps/test_roadmap_step_fix_checks_repair.py`
- [x] 1.2 Add `judge_scope`, `changed_definitions` and `read_branch_change` in `src/devops_cli/roadmap/steps/fix_checks_cause.py`; make `check_scope` return a `ScopeVerdict`; give the model fix the extra paths through `FixRequest.extra_paths`, which the fix group names and the outside-plan check allows; and post the comment that names the files of a pushed repair
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_fix_checks_cause.py tests/roadmap/steps/test_roadmap_step_fix_checks.py tests/roadmap/steps/test_roadmap_step_fix_checks_repair.py`

## 2. Write snapshots and documents again in tier 1

Kind: behavior. Changes: `src/devops_cli/roadmap/toolchains.py`, `src/devops_cli/roadmap/steps/fix_checks.py`, `src/devops_cli/roadmap/steps/fix_checks_repair.py`, `tests/roadmap/steps/test_fix_checks_cause.py`, `tests/roadmap/steps/test_roadmap_step_fix_checks_repair.py`.

- [x] 2.1 Write the failing case from the text of #6041: the log of a failed syrupy snapshot gives tier 1 the test file, and tier 1 runs the snapshot update, `devops docs generate`, the test and the docs check, and names the two files that it wrote
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_step_fix_checks_repair.py`
- [x] 2.2 Add `snapshot_update` to the toolchain preset, the cause `snapshots` to `Tier1Causes`, and the commands to `tier1_commands`; return the written files in `Fixed.files`
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_step_fix_checks_repair.py`

## 3. Documents

Kind: other. Changes: `docs/adr/0021-the-roadmap-service-is-a-webhook-router-cluster-pods-run-the-roadmap-jobs-and-valkey-holds-their-shared-state.md`.

- [x] 3.1 Regenerate the documents for the new message, and add the dated line of the out-of-date tier facts to the Status History of ADR 0021
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
