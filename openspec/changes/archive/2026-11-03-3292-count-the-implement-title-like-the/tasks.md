# Tasks

## 1. Check the delivery title before the job writes it

Reads: `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/pull_form.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_implement_job.py`. Changes: `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_implement_job.py`.

- [x] 1.1 In `tests/roadmap/test_roadmap_implement_job.py`, add `test_a_title_that_the_check_refuses_stops_the_item_before_the_job_writes_it`: patch `delivery_title` to return `Add a flag: `, run `two_groups`, and assert that the item stops at `pull_request`, sends no `PATCH pulls/5` and posts the form problem
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_job.py` fails on the base
- [x] 1.2 In `src/devops_cli/roadmap/implement_run.py`, call `title_problems` on the delivery title in `_delivery_title`. On a problem, raise `_StopError` with the new `implement_stop_title_refused` message and `push=False`. In `_publish`, compute the title before `git push`, so a stop leaves no branch on `origin`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_job.py` passes

## 2. State the implement title limit in code units

Reads: `openspec/specs/roadmap-implement-job/spec.md`. Changes: `openspec/specs/roadmap-implement-job/spec.md`.

- [x] 2.1 In `openspec/specs/roadmap-implement-job/spec.md`, change the requirement `The pull request that delivers the code has the type of the issue` so its text says that the title holds the whole summary, that the form checks 60 UTF-16 code units, and that the job stops on a title that the form refuses. Change the scenario `A long summary` to 61 units and add the scenarios for a summary of 60 units and for a summary of 80 units of emoji. Keep the other scenarios
  - Verification: `uv run devops openspec check` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
