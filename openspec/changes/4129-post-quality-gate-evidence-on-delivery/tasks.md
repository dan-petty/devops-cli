# Tasks

## 1. Answer the pull request read with the head that the pull fake holds

Kind: other. Reads: `src/devops_cli/github/pr_evidence.py`, `tests/support/roadmap_implement.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`. Changes: `tests/support/roadmap_implement.py`.

- [ ] 1.1 In `tests/support/roadmap_implement.py`, answer the REST read of pull request 5 with the head commit that the pull fake holds, and route the REST check runs of that head with the passing run, so `publish_pr_evidence` reads the same head that `_ready` reads. The comment listing and the comment create of the pull request are routed already, and the login read answers the bot. The finish test of `tests/roadmap/implement/test_roadmap_implement_job.py` keeps passing
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job.py` passes

## 2. Publish the delivery evidence before the ready mark

Kind: behavior. Reads: `src/devops_cli/github/pr_evidence.py`, `src/devops_cli/exceptions/git.py`, `tests/support/roadmap_implement.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`, `tests/roadmap/implement/test_roadmap_implement_body_retry.py`, `tests/roadmap/implement/test_roadmap_implement_job_recorded_tests.py`, `tests/roadmap/implement/test_roadmap_implement_strength.py`, `tests/roadmap/implement/test_roadmap_implement_title_sync.py`, `tests/roadmap/implement/test_roadmap_implement_typed_result.py`, `tests/roadmap/implement/test_roadmap_implement_write_stops.py`, `tests/roadmap/test_roadmap_faults.py`. Changes: `src/devops_cli/roadmap/implement/implement_run.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`.
Adds: `_publish_evidence`

- [ ] 2.1 Write two failing tests in `tests/roadmap/implement/test_roadmap_implement_job.py`: `test_the_job_posts_the_evidence_before_it_marks_the_pull_request_ready`, which records the comment listing at the moment of the ready call and asserts that the evidence comment is there before the run ends ready; and `test_a_failed_evidence_post_stops_the_item_before_ready`, which makes the publisher raise a Git Hub operation error and asserts that the item is Blocked, that the ready call list is empty and that the pull request stays a draft
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job.py` fails on the base
- [ ] 2.2 Add `_publish_evidence` to the job class in `src/devops_cli/roadmap/implement/implement_run.py`: it calls `publish_pr_evidence(get_git_hub_session(), self.repo, pull)` and, on a `GitHubOperationError`, raises `_error_stop(self.step, exc) from exc`, so the item is Blocked and the pull request stays a draft. Call it in `_ready` after `src/devops_cli/roadmap/implement/implement_run.py:2094:if readiness.answer is not Answer.READY:` and before `src/devops_cli/roadmap/implement/implement_run.py:2097:mark_ready(self.repo, pull, draft=draft)`. Add no message and no second renderer. The world answers the head and the comment listing that the publisher reads
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job.py` passes

## 3. Name the evidence step in the workflow documents

Kind: other. Reads: `src/devops_cli/roadmap/implement/implement_run.py`. Changes: `CONTEXT.md`, `docs/ROADMAP_WORKFLOW.md`.

- [ ] 3.1 Edit `CONTEXT.md` so the Implementing entry names the evidence comment that the job posts before the ready mark, and edit `docs/ROADMAP_WORKFLOW.md` so the verify step of the runner Job names the evidence comment before the ready mark. Write the final behavior only: the comment is posted before the pull request leaves draft, and a failed post stops the item
  - Verification: `$ uv run devops ci docs` passes
- [ ] 3.2 Edit `CONTEXT.md` and `docs/ROADMAP_WORKFLOW.md` to name the evidence comment before the ready mark
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
