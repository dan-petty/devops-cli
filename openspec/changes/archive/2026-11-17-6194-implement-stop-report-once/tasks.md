# Tasks

## 1. The page of a posted comment

Kind: behavior. Changes: `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stores/github_store.py`, `src/devops_cli/roadmap/stores/comment_repeat.py`, `src/devops_cli/roadmap/steps/comment.py`, `tests/support/fakes/roadmap_store.py`, `tests/support/fakes/github_repository.py`.

- [x] 1.1 Add the failing tests in `tests/roadmap/stores/test_roadmap_store_contract.py`: a comment gives the page of the new comment, and a refused repeat gives the page of the earlier comment, over the fake and over the GitHub store
  - Verification: `$ uv run devops ci test tests/roadmap/stores/test_roadmap_store_contract.py`
- [x] 1.2 Add `PostedComment`, give it from `comment()` of both stores with the page that GitHub answers, give the earlier comment from `refused_repeat`, and answer a comment of the GitHub fake with its id and page
  - Verification: `$ uv run devops ci test tests/roadmap/stores/`

## 2. The stop report on the issue, once

Kind: behavior. Changes: `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/implement/implement_submit.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/lang/en/messages.py`.

- [x] 2.1 Add the failing tests in `tests/roadmap/implement/test_roadmap_implement_job_table.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`, `tests/roadmap/implement/test_roadmap_implement_submit.py` and `tests/roadmap/test_roadmap_dry_runs.py`: the comment of a stopped run links the stop comment and holds no table, the round posts no Job report after a result, a retry clears one stop and never loops, and the dry run lists the writes of a stop in order
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job_table.py tests/roadmap/implement/test_roadmap_implement_job.py tests/roadmap/implement/test_roadmap_implement_submit.py tests/roadmap/test_roadmap_dry_runs.py`
- [x] 2.2 Post the stop comment on the issue first and give the comment of the run the link line in place of the table, comment a Job report only for a Job with no result or a Job that is gone, and list the writes of a stop in the dry run
  - Verification: `$ uv run devops ci test tests/roadmap/implement/ tests/roadmap/test_roadmap_dry_runs.py tests/roadmap/test_roadmap_stop_clear.py`

## 3. The verdict of a discard on the issue

Kind: behavior. Changes: `src/devops_cli/roadmap/steps/review.py`, `src/devops_cli/roadmap/return_item.py`.

- [x] 3.1 Add the failing test in `tests/roadmap/steps/test_roadmap_step_review.py`: the return comment of a discard holds the reason and the evidence, and the comment of the step on the pull request links it
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_step_review.py`
- [x] 3.2 Give the verdict to the return comment, give the posted comment from `apply_return`, and change the comment of the step on the pull request to the link
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_step_review.py tests/roadmap/test_roadmap_return.py`

## 4. Documents

Kind: other. Changes: `docs/roadmap/implement.md`, `docs/CLUSTER.md`.

- [x] 4.1 Describe the stop report on the issue, the link on the pull request, the Job report after no result, and the retry that clears one stop
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
