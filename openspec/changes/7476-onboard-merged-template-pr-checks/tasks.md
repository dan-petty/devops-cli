# Tasks

## 1. Read the checks of the open template pull request only

Kind: behavior. Reads: `src/devops_cli/github/onboard/template_pr.py`, `src/devops_cli/github/onboard/settings_rows.py`, `src/devops_cli/github/onboard/run.py`, `tests/github/onboard/test_onboard_rows.py`, `tests/support/github_repository.py`. Changes: `src/devops_cli/github/onboard/template_pr.py`, `tests/github/onboard/test_onboard_rows.py`.
Removes: `_last_template_pull`

- [x] 1.1 `test_a_template_pull_request_that_is_not_open_gives_row_10_no_check`, which covers the scenarios `A merged template pull request with a check name that no workflow reports now` and `A merged template pull request of an onboarded repository`, and `test_a_live_required_check_that_only_skipped_is_dropped`, `test_a_live_matrix_leg_gives_way_to_its_job_name` and `test_a_plan_reports_a_required_check_that_only_skipped`, which cover the scenarios `An open template pull request of an onboarded repository` and `A live required check that only a skipped check run gave`, in `tests/github/onboard/test_onboard_rows.py`, and the case `test_a_second_confirmed_run_on_a_new_repository_writes_nothing` of that module, which must keep passing
  - Verification: `$ uv run devops ci test tests/github/onboard/test_onboard_rows.py` fails on the base
- [x] 1.2 Write the cases first in `tests/github/onboard/test_onboard_rows.py`: replace `_merged_template_pull` with `_template_pull`, which takes the state of the pull request; give the three drop cases an open template pull request; and add a confirmed run over rows 9 and 10 of an onboarded repository whose merged or closed template pull request reported `Semantic PR title` as `success`, or `K8s` as `skipped` while the live ruleset requires `K8s`, which must leave rows 9 and 10 `present` and send no write. In `src/devops_cli/github/onboard/template_pr.py`, make `template_row` read the check runs of the pull request of `_open_pull` when the repository holds each template file, delete `_last_template_pull`, and state the rule in the module docstring and in the docstring of `template_row`
  - Verification: `$ uv run devops ci test tests/github/onboard/test_onboard_rows.py` passes

## 2. State the check rule of rows 9 and 10

Kind: other. Reads: `docs/repos/onboard.md`, `src/devops_cli/github/onboard/template_pr.py`. Changes: `docs/repos/onboard.md`.

- [x] 2.1 In `docs/repos/onboard.md`, state in the row 9 entry that the row reads the check runs of the open template pull request and that a merged or closed one gives row 10 no check; state in the row 10 entry that with no open template pull request the row keeps each live check; and say in the person step of a dropped check that a required check of a repository whose template pull request merged stays until a person removes it from the ruleset
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
- Pending a person: run `uv run devops repos onboard dan-petty/devtools --plan --only 9,10` with the token of the owner, and see that row 10 does not add `Semantic PR title`.
