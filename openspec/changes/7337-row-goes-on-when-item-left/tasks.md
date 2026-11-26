# Tasks

## 1. The store gives one result for a number that is no issue of the repository

Kind: behavior. Reads: `src/devops_cli/github/error_classifier.py`, `src/devops_cli/github/repo_ref.py`, `src/devops_cli/roadmap/stores/listing_snapshot.py`, `src/devops_cli/roadmap/stores/comment_repeat.py`. Changes: `src/devops_cli/exceptions/git.py`, `src/devops_cli/exceptions/__init__.py`, `src/devops_cli/github/issue_answer.py` (new), `src/devops_cli/roadmap/stores/github_store.py`, `tests/support/fakes/github.py`, `tests/support/fakes/github_repository.py`, `tests/support/fakes/roadmap_store.py`, `tests/roadmap/stores/test_roadmap_github_store_issue_answer.py`, `tests/roadmap/stores/test_roadmap_store_contract.py`.
Adds: `GitHubNotAnIssueError`, `NO_ISSUE_STATUSES`, `answered_repository`, `answers_request`, `GitHubRoadmapStore._listing_below`

- [x] 1.1 Give `GitHubFake.move_issue` the option `followed`, whose false value answers the issue route with `gh: HTTP 301`, and make `RunnerSession` raise `GitHubNotFoundError` for a 404 of a listing, as the real session does. Add the failing cases to `tests/roadmap/stores/test_roadmap_github_store_issue_answer.py`: a plain read and a conditional read that answer 301, 410 or 404, a conditional read whose status line is 301, a 404 below a number of no issue and of an issue of the repository, a job comment on no issue, the drop of the record at a 404 of the comments and of the events, the one log line with the place of the answer, and a redirect of another route, which passes on the base
  - Verification: `$ uv run devops ci test tests/roadmap/stores/test_roadmap_github_store_issue_answer.py` fails on the base
- [x] 1.2 Add `GitHubNotAnIssueError` to `src/devops_cli/exceptions/git.py`. Move the comparison of an answer to `src/devops_cli/github/issue_answer.py` with `NO_ISSUE_STATUSES`. In `github_store.py`, raise the class in `_not_an_issue`, read one issue with the statuses of `NO_ISSUE_STATUSES` as absent in `_read_issue` and `_revalidate_issue`, read `comments_on`, `label_changes` and `blocked_by` through `_listing_below`, and log one line for a number in `_gone`. Make `InMemoryRoadmapStore` raise the class
  - Verification: `$ uv run devops ci test tests/roadmap/stores/test_roadmap_github_store_issue_answer.py tests/roadmap/stores/test_roadmap_store_contract.py tests/roadmap/stores/test_github_store_brain.py` passes

## 2. A row leaves out an item that is no issue of the repository

Kind: behavior. Reads: `src/devops_cli/roadmap/status_sync.py`, `src/devops_cli/roadmap/stop_clear.py`, `src/devops_cli/roadmap/implement/implement_submit.py`, `src/devops_cli/roadmap/stage/stage_job_phases.py`, `src/devops_cli/roadmap/planned.py`, `src/devops_cli/roadmap/run.py`. Changes: `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/plan_drift.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_rows_issue_answer.py`, `tests/roadmap/stage/test_roadmap_stage_prepare.py`, `tests/roadmap/stage/test_roadmap_stage_drift.py`.

- [x] 2.1 Add the failing cases of the rows to `tests/roadmap/test_roadmap_rows_issue_answer.py`: an alternatives round with one item that left and one other due item, with an item whose comments answer 404, and with 10 items that left, and the three Status passes of the row `implement` with one item whose issue route redirects and whose comments route answers 404. Add the case of a stage Job with an active change folder whose issue answers 301, and the same with the issue at its new place, to `tests/roadmap/stage/test_roadmap_stage_prepare.py`, and the case of a plan pull request whose issue left to `tests/roadmap/stage/test_roadmap_stage_drift.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_rows_issue_answer.py tests/roadmap/stage/test_roadmap_stage_prepare.py tests/roadmap/stage/test_roadmap_stage_drift.py` fails on the base
- [x] 2.2 Leave the item out in `write_each` of `src/devops_cli/roadmap/stage/stage.py`, in `_settled` of `src/devops_cli/roadmap/alternatives.py` and in `run_plan_drift` of `src/devops_cli/roadmap/stage/plan_drift.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_rows_issue_answer.py tests/roadmap/stage/test_roadmap_stage_prepare.py tests/roadmap/stage/test_roadmap_stage_drift.py tests/roadmap/test_roadmap_stop_clear.py` passes

## 3. A delivery that says that an issue left drops its record at once

Kind: behavior. Reads: `src/devops_cli/roadmap/stores/brain_issues.py`, `src/devops_cli/roadmap/stores/listing_snapshot.py`. Changes: `src/devops_cli/models/webhooks.py`, `src/devops_cli/server/routes/webhooks.py`, `src/devops_cli/server/service.py`, `src/devops_cli/roadmap/run.py`, `tests/server/routes/test_webhooks_brain.py`, `tests/server/test_server_service.py`, `tests/roadmap/test_roadmap_rows_issue_answer.py`.
Adds: `issue_left`, `TriggerBatch.left`

- [x] 3.1 Add the failing cases: a delivery `issues` with the action `transferred` and one with `deleted` remove the brain entry (`tests/server/routes/test_webhooks_brain.py`), a batch names the numbers that left (`tests/server/test_server_service.py`), and the round of a lane drops the record of such a number with no GitHub read (`tests/roadmap/test_roadmap_rows_issue_answer.py`)
  - Verification: `$ uv run devops ci test tests/server/routes/test_webhooks_brain.py tests/server/test_server_service.py tests/roadmap/test_roadmap_rows_issue_answer.py` fails on the base
- [x] 3.2 Add `issue_left` to `src/devops_cli/models/webhooks.py`. Remove the entry in the roadmap consumer of `src/devops_cli/server/routes/webhooks.py`, keep the numbers in `TriggerBatch.left` in `src/devops_cli/server/service.py`, and drop them from the listing in `service_job` of `src/devops_cli/roadmap/run.py`
  - Verification: `$ uv run devops ci test tests/server/routes/test_webhooks_brain.py tests/server/test_server_service.py tests/roadmap/test_roadmap_rows_issue_answer.py` passes

## 4. The other readers of one issue number compare the answer

Kind: behavior. Reads: `src/devops_cli/roadmap/release_comments.py`, `src/devops_cli/roadmap/plan_check.py`, `src/devops_cli/roadmap/job_funnel.py`, `src/devops_cli/roadmap/stage/stage_github_snapshot.py`, `src/devops_cli/roadmap/stage/stage_github.py`. Changes: `src/devops_cli/roadmap/release_feed.py`, `src/devops_cli/github/client.py`, `tests/roadmap/test_roadmap_release_feed.py`, `tests/github/test_github_client_issue_reads.py`.

- [x] 4.1 Add the failing cases: a closed issue of a release that left the repository (`tests/roadmap/test_roadmap_release_feed.py`), and an answer of the client that names another issue (`tests/github/test_github_client_issue_reads.py`)
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_release_feed.py tests/github/test_github_client_issue_reads.py` fails on the base
- [x] 4.2 Compare the answer in `GitHubReleaseFeed._issue` and in `GitHubClient.get_issue` with `answers_request`, and take the statuses of `NO_ISSUE_STATUSES` as absent in the feed
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_release_feed.py tests/github/test_github_client_issue_reads.py tests/roadmap/test_roadmap_release_comments.py` passes

## 5. Give the rule in the documents

Kind: other. Reads: `docs/CLUSTER.md`. Changes: `docs/CLUSTER.md`, `docs/ERRORS.md`.

- [x] 5.1 Give the rule of this change in the paragraph of `docs/CLUSTER.md` about the issue cache, and write `docs/ERRORS.md` again with `uv run devops docs generate`
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
