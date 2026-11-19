# Tasks

## 1. Publish the evidence of the head commit that the caller gives

Kind: behavior. Reads: `src/devops_cli/github/pr_evidence.py`, `src/devops_cli/commands/pr.py`, `tests/github/test_pr_evidence.py`, `tests/commands/test_pr_evidence.py`, `tests/commands/test_pr.py`, `tests/commands/test_pr_cmd.py`, `tests/commands/test_pr_describe.py`, `tests/commands/test_pr_dry_run.py`, `tests/commands/test_pr_form_check.py`, `tests/commands/test_pr_other_repository.py`, `tests/commands/test_pr_status.py`, `tests/commands/test_pr_title_labels.py`, `tests/commands/test_pr_update.py`. Changes: `src/devops_cli/github/pr_evidence.py`, `src/devops_cli/commands/pr.py`, `tests/github/test_pr_evidence.py`.

- [x] 1.1 Write the failing test `test_publish_names_the_head_that_the_caller_gives` in `tests/github/test_pr_evidence.py` first: the pull request payload holds an empty head sha, the caller passes `head=_SHA`, and the comment names `_SHA` while the check-runs read is the one of `_SHA`
  - Verification: `$ uv run devops ci test tests/github/test_pr_evidence.py tests/commands/test_pr_evidence.py` fails on the base
- [x] 1.2 Add the keyword-only argument `head: str | None = None` to `src/devops_cli/github/pr_evidence.py:96:def publish_pr_evidence(`, and use `head or pull.head.sha` for the check-runs read and for `head_sha` of the comment. The call site at `src/devops_cli/commands/pr.py:495:publish_pr_evidence(` passes no head, so the command keeps publishing the head of the pull request that it reads, and its docstring at `src/devops_cli/commands/pr.py:479:"""Write the check results of the head commit of a pull request as its one evidence comment.` names the head commit that it publishes
  - Verification: `$ uv run devops ci test tests/github/test_pr_evidence.py tests/commands/test_pr_evidence.py` passes

## 2. Publish the delivery evidence before the ready mark

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/github/pr_evidence.py`, `src/devops_cli/roadmap/implement/implement_pull.py`, `tests/support/roadmap_implement.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`, `tests/roadmap/implement/test_roadmap_implement_phase_marks.py`, `tests/roadmap/implement/test_roadmap_implement_body_retry.py`, `tests/roadmap/implement/test_roadmap_implement_job_recorded_tests.py`, `tests/roadmap/implement/test_roadmap_implement_strength.py`, `tests/roadmap/implement/test_roadmap_implement_title_sync.py`, `tests/roadmap/implement/test_roadmap_implement_typed_result.py`, `tests/roadmap/implement/test_roadmap_implement_write_stops.py`, `tests/roadmap/test_roadmap_faults.py`. Changes: `src/devops_cli/roadmap/implement/implement_run.py`, `tests/support/roadmap_implement.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`, `tests/roadmap/implement/test_roadmap_implement_phase_marks.py`.
Adds: `_publish_evidence`

- [ ] 2.1 Write the failing tests `test_the_job_changes_the_evidence_comment_before_it_marks_the_pull_request_ready` and `test_a_failed_evidence_change_stops_the_item` in `tests/roadmap/implement/test_roadmap_implement_job.py` first. The first runs the job to the end and asserts that the one change of comment 900 names the head of the branch, that no posted comment of the pull request opens with the marker, and that the change of comment 900 is in the request list that the one ready call recorded, so it fails when the evidence is written after the ready mark. The second routes the change of comment 900 to a 422 so that the publisher raises a `GitHubOperationError`, and asserts that the run stopped the item, that Status is Blocked, that the record names the ready step as the stopped step, and that `job_world.pull.ready_calls` is empty
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job.py tests/roadmap/implement/test_roadmap_implement_phase_marks.py` fails on the base
- [ ] 2.2 Add `_publish_evidence` to `_ItemRun` at `src/devops_cli/roadmap/implement/implement_run.py:633:class _ItemRun:`. It calls `publish_pr_evidence(get_github_session(), self.repo, pull, head=head)` and, on a `GitHubOperationError` at `src/devops_cli/exceptions/git.py:86:class GitHubOperationError(DevOpsCLIError, RuntimeError):`, raises the stop at `src/devops_cli/roadmap/implement/implement_run.py:302:class _StopError(Exception):` from the error with its text as the reason. Call it in `_ready` between the readiness answer and `src/devops_cli/roadmap/implement/implement_run.py:2097:mark_ready(self.repo, pull, draft=draft)`, with the head that the step read at `src/devops_cli/roadmap/implement/implement_run.py:2055:head = status.head_sha or self._head()`. In `tests/support/roadmap_implement.py`, seed one comment of id 900 whose body opens with the marker and whose author is the world's login, route the change of `issues/comments/900`, list that seed ahead of the comments that a test gives, and record in a new `ready_requests` list the `self.api.requested` snapshot at each `gh pr ready`. In `tests/roadmap/implement/test_roadmap_implement_phase_marks.py`, update the three request-count assertions to the extra evidence listing read and the evidence change, including the request bound of the marker test
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job.py tests/roadmap/implement/test_roadmap_implement_phase_marks.py` passes

## 3. Name the evidence step in the workflow documents

Kind: other. Reads: `CONTEXT.md`, `docs/ROADMAP_WORKFLOW.md`, `tests/invariants/test_roadmap_workflow_doc.py`. Changes: `CONTEXT.md`, `docs/ROADMAP_WORKFLOW.md`.

- [ ] 3.1 Edit the Implementing entry of `CONTEXT.md` so its list of the run names the evidence comment of the pull request before `gh pr ready`. Edit the Verify row of `docs/ROADMAP_WORKFLOW.md` so it says that the runner Job publishes the check-results comment of the head commit before it marks the pull request ready, and that a failed write stops the item
  - Verification: `$ uv run devops ci docs` passes
- [ ] 3.2 Edit `CONTEXT.md` and `docs/ROADMAP_WORKFLOW.md` to name the evidence comment of the head commit before the ready mark
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
