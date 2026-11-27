# Tasks

## 1. Require only the check runs that ended success

Kind: behavior. Reads: `src/devops_cli/github/onboard/settings_rows.py`, `src/devops_cli/github/onboard/template_pr.py`, `src/devops_cli/github/onboard/model.py`, `tests/github/onboard/test_onboard_rows.py`, `tests/support/github_repository.py`, `tests/github/onboard/test_onboard_openspec.py`, `tests/github/onboard/test_onboard_routes.py`, `tests/infra/test_onboard.py`. Changes: `src/devops_cli/github/onboard/template_pr.py`, `src/devops_cli/github/onboard/model.py`, `src/devops_cli/github/onboard/settings_rows.py`, `tests/github/onboard/test_onboard_rows.py`.
Adds: `_LEG_PATTERN`, `_check_base_name`, `_checks_to_require`

- [x] 1.1 `test_a_skipped_check_run_is_no_required_check`, which covers the scenarios `Skipped reusable-workflow job` and `Passing check`, and `test_a_matrix_leg_gives_way_to_its_job_name`, which covers `Skipped matrix legs` and `Passing matrix legs`, in `tests/github/onboard/test_onboard_rows.py`, and the case `test_a_confirmed_run_requires_the_checks_of_the_repository_file` of that module, which must keep passing
  - Verification: `$ uv run devops ci test tests/github/onboard/test_onboard_rows.py` fails on the base
- [x] 1.2 Write the cases first in `tests/github/onboard/test_onboard_rows.py`: a confirmed run over rows 9 and 10 whose check runs hold `K8s` as `skipped` and `Lint` as `success`, one whose check run `Tests` ended `success`, and one whose check runs hold `Tests & Coverage` as `success` with its leg `Tests & Coverage (shard 1 of 5)`, once as `skipped` and once as `success`; each asserts the required checks of `harness.state.rulesets[0]`. In `src/devops_cli/github/onboard/template_pr.py`, add `successful` and `skipped` to `_Checks`, fill them in `_read_checks` from the runs whose conclusion is `success` and `skipped`, and set `ctx.successful_checks` and `ctx.skipped_checks` in `_checks_row`. In `src/devops_cli/github/onboard/model.py`, replace `reported_checks` with `successful_checks` and add `skipped_checks` to `RowContext`. In `src/devops_cli/github/onboard/settings_rows.py`, add `_LEG_PATTERN`, `_check_base_name` and `_checks_to_require`, take the successful names in place of `reported` in `_with_required_checks`, and add only the names of `_checks_to_require`; state the new rule in the docstring of `_with_required_checks`
  - Verification: `$ uv run devops ci test tests/github/onboard/test_onboard_rows.py` passes

## 2. Audit a repository that onboard already changed

Kind: behavior. Reads: `src/devops_cli/github/onboard/settings_rows.py`, `src/devops_cli/github/onboard/template_pr.py`, `src/devops_cli/github/onboard/model.py`, `src/devops_cli/github/onboard/run.py`, `src/devops_cli/github/onboard/drift.py`, `tests/github/onboard/test_onboard_rows.py`, `tests/support/github_repository.py`, `tests/infra/test_onboard.py`. Changes: `src/devops_cli/github/onboard/template_pr.py`, `src/devops_cli/github/onboard/settings_rows.py`, `tests/support/github_repository.py`, `tests/github/onboard/test_onboard_rows.py`.
Adds: `_last_template_pull`, `_dropped_checks`

- [x] 2.1 `test_a_live_required_check_that_only_skipped_is_dropped`, which covers the scenario `A live required check that only a skipped check run gave`, `test_a_live_matrix_leg_gives_way_to_its_job_name`, and `test_an_onboarded_repository_reports_a_required_check_that_only_skipped`, which covers the scenario `A merged template pull request of an onboarded repository`, in `tests/github/onboard/test_onboard_rows.py`, and the cases `test_an_onboarded_repository_plans_no_change` and `test_a_second_confirmed_run_on_a_new_repository_writes_nothing` of that module, which must keep passing
  - Verification: `$ uv run devops ci test tests/github/onboard/test_onboard_rows.py` fails on the base
- [x] 2.2 Write the cases first in `tests/github/onboard/test_onboard_rows.py`: a confirmed run whose live ruleset requires `K8s` and whose template pull request reported `K8s` as `skipped`; a confirmed run whose live ruleset requires `Tests & Coverage (shard 1 of 5)` and whose template pull request reported its job as `success`; and a plan run over rows 9 and 10 of a repository that `state.onboard` leaves as a merged template pull request with `K8s` as `skipped`, which must be `pending` with `; dropped K8s` and send no write. In `tests/support/github_repository.py`, make `_pulls` return the pull requests of the state that the query names, so `state=all` serves the merged template pull request. In `src/devops_cli/github/onboard/template_pr.py`, add `_last_template_pull`, which lists the pull requests of the head `ci/repository-template` in any state and gives the newest, and make `template_row` read its head's check runs when the repository holds each template file, recording `ctx.successful_checks` and `ctx.skipped_checks`. In `src/devops_cli/github/onboard/settings_rows.py`, add `_dropped_checks`, make `_with_required_checks` return the desired ruleset and the live checks that it leaves out while it keeps each check that the baseline settings file names, and make `ruleset_row` append `; dropped` and those names to its change line
  - Verification: `$ uv run devops ci test tests/github/onboard/test_onboard_rows.py` passes

## 3. State the check rules of rows 9 and 10

Kind: other. Reads: `docs/repos/onboard.md`, `src/devops_cli/github/onboard/settings_rows.py`, `src/devops_cli/github/onboard/template_pr.py`. Changes: `docs/repos/onboard.md`.

- [x] 3.1 In `docs/repos/onboard.md`, state in the row 9 entry that the row reads the check runs of the newest template pull request, merged included, when the repository holds each template file. State in the row 10 entry that a required check comes only from a check run that ended `success`, that a matrix leg gives way to the name of its job, that a live required check that only a skipped check run gave leaves the set, and that the change line names it after `; dropped`. Say that a check that a repository needs goes in the settings file of its baseline. Add a person step for a repository whose row 10 reports a dropped check: run `devops repos onboard <owner>/<name> --confirm --only 9,10`, and say that the nightly drift run reports such a check for each repository of `service.repos`
  - Verification: `$ uv run devops ci docs` passes
- [x] 3.2 Edit `docs/repos/onboard.md` to state the rule of the required checks of rows 9 and 10, and the person step that removes a reported check
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
