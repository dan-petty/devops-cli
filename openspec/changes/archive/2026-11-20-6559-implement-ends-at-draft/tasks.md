# Tasks

## 1. The run ends at the draft

Kind: behavior.

- [x] 1.1 Write failing tests: a run whose groups pass records `drafted`, sets In Review and sends no `gh pr ready`; a stopped step resets to its start with no `wip:` commit; the watch row and the step `fix-checks` take a drafted draft; the intended result of `implement` is `drafted`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job.py tests/roadmap/implement/test_roadmap_implement_step.py tests/roadmap/test_roadmap_watch_row.py tests/roadmap/steps/test_roadmap_step_fix_checks.py tests/roadmap/test_job_result.py`
- [x] 1.2 End the run at the draft (`_end_drafted`), delete `implement_wip.py`, `_keep`, `_move_wip`, the in-Job loop and the watch of `implement_pull.py`, add `takes_ready_path`, and set `drafted` as the intended result
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job.py tests/roadmap/implement/test_roadmap_implement_step.py tests/roadmap/test_roadmap_watch_row.py tests/roadmap/steps/test_roadmap_step_fix_checks.py tests/roadmap/test_job_result.py`

## 2. The records, the counter and the setting of the old flow

Kind: other.

- [x] 2.1 Delete `implement.wip`, `implement.continued`, `devops_cli_service_kept_work_total`, `roadmap.implement.monitor_timeout_seconds` and the tests that cover only them
  - Verification: `! git grep -n -e implement_wip -e KEPT_WORK -e monitor_timeout_seconds -e ImplementRecordKey.WIP src/ tests/`

## 3. The forge outcome and the hand-off

Kind: behavior.

- [x] 3.1 Write failing tests: the report scores the drafted lines of each pull request once by its forge state; the read gives the item, the state and the draft flag; the row stops a delivery draft whose check or conflict has no repair owner (mode, class, ended unit, Staged, claim, latest run); a stop gives no ready mark; a refused draft stops at `ready`; a ready path that raises runs again; a drafted item is in review until it is marked ready
  - Verification: `$ uv run devops ci test tests/roadmap/test_job_grade_report.py tests/roadmap/test_pr_verdict.py tests/roadmap/test_roadmap_watch_row.py tests/roadmap/steps/test_roadmap_due_steps.py tests/roadmap/test_roadmap_phase.py tests/roadmap/implement/test_roadmap_implement_job.py`
- [x] 3.2 Score the drafted lines in `job_grade_report.py`, read the forge state in `pr_verdict.py`, add the due step `stop` and its stop in `watch_row.py`, add `_require_complete`, move the judged head after the report, and map a drafted item to `in-review`
  - Verification: `$ uv run devops ci test tests/roadmap/test_job_grade_report.py tests/roadmap/test_pr_verdict.py tests/roadmap/test_roadmap_watch_row.py tests/roadmap/steps/test_roadmap_due_steps.py tests/roadmap/test_roadmap_phase.py tests/roadmap/implement/test_roadmap_implement_job.py`

## 4. Documents

Kind: other.

- [x] 4.1 Change `docs/roadmap/job-success.md`, `docs/roadmap/implement.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/CLUSTER.md`, `CONTEXT.md`, `k8s/README.md` and the step prompt, and regenerate the documentation
  - Verification: `$ uv run devops ci docs`

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
