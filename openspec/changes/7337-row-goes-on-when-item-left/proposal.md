# Proposal: #7337

## Why

An issue can leave a repository: a person transfers it or deletes it (#7337). The listing snapshot of each lane keeps its record as an open item until the next full read, at most 24 hours later. The store gives no issue for such a number, and the lane drops the record at its first issue read. Five gaps stay:

- A round fails for the item. The alternatives round raised the error of a missing issue at its body read. The stop pass of the row `implement` listed the comments of the item, got 404, and the row raised `the Status of 1 item(s) could not be set`. After 6 failed rounds a row runs one probe round each hour, so a transfer of many issues stops a lane for hours.
- A read below the number drops nothing. `comments_on`, `label_changes` and `blocked_by` answer 404 for such a number, and the store kept the record, so the round failed at each run.
- A read can end with status 301. In a runner Job, `gh api repos/<repository>/issues/<number>` did not follow the redirect of a transferred issue and ended with `gh: HTTP 301`. The store took only 404 as an absent issue. Each stage Job of the repository reads the issue of each active change folder, so each stage Job failed with exit code 75 and the class `ci_infra` while the default branch held the change folder of a transferred issue.
- The webhook route does not use the event. GitHub sends an `issues` delivery with the action `transferred` or `deleted`. The route wrote a brain entry from that payload, and each lane learned of the change only at its own read.
- Other readers of one issue number compare nothing. The release feed and `GitHubClient.get_issue` took the answer for a transferred issue as the issue that they asked for.

## What Changes

- One error class, `GitHubNotAnIssueError`, is the result of a number that is no issue of the repository. `GitHubRoadmapStore` raises it where it raised `GitHubOperationError` with the message `#<number> is not an issue of <repository>.`. The message and the details stay. The class is a `GitHubNotFoundError`, and its code is `GITHUB_NOT_AN_ISSUE`.
- The store takes the statuses 301 and 410 of a read of one issue by its number as 404: the plain read and the conditional read give no issue and drop the record. A listing of the repository or another route that answers 301 or 410 fails as before.
- An answer with the requested number and another repository name is the requested issue when GitHub gives the repository of the reader that name now (a renamed repository). The reader reads `repos/<its repository>` one time for that, takes the answer and logs one warning that its name is old. Before, a rename read as "each item left".
- `comments_on`, `label_changes` and `blocked_by` read the issue when their listing answers 404, 410 or 301. When that read gives no issue of the repository, the store has dropped the record, and the call raises `GitHubNotAnIssueError`. Else the 404 stays the error of the listing.
- The store logs one line for a number that it leaves out, with the repository and the number of the answer when the answer names them.
- The rows leave such an item out and go on. `write_each`, which runs the Status sweep, the clear of the closed issues and the stop pass of the row `implement`, the removals of the row `stage`, `mark_stage_ready` and `devops roadmap repair`, records no failure for it. The alternatives round gives it no check and no failure. The planner and `prepare` of the stage job give it no result, no failure class and no failure mark. The plan drift row leaves out a plan pull request whose issue is no issue of the repository.
- The webhook route removes the brain entry of the issue of an `issues` delivery with the action `transferred` or `deleted`, and writes none from its payload. The trigger batch of each lane names the number in `TriggerBatch.left`, and the round of the lane drops the record from its listing before any row runs. A delivery of the bot of the App for these two actions removes the entry too.
- The release feed and `GitHubClient.get_issue` compare the answer with the request by the comparison of the store, which moves to `src/devops_cli/github/issue_answer.py`. The client raises `GitHubNotAnIssueError` for the status 410 and for a 301 that it does not follow.
- `docs/CLUSTER.md` gives the rule in its paragraph about the issue cache.

A consumer observes the result of a read, the class of an error, the log line and the result of a round, so the change carries spec deltas. It fits one pull request.

## Capabilities

### Modified Capabilities

- `roadmap-store-issue-read`: An issue read compares the answer with the request, A write is refused when its read answers with another issue, A row sends no write for an item whose read answers with another issue (modified); A refused answer logs the requested number (removed); A number that is no issue is logged one time, A read that answers 301 or 410 gives no issue, A listing below a number that answers 404, 410 or 301 reads the issue, A row leaves out an item that is no issue of the repository, Other readers of one issue number compare the answer, An answer under the old name of a renamed repository is the requested issue, The stage Job goes on when the issue of an active change folder left (added)
- `roadmap-intake-listing`: A delivery that says that an issue left drops its record in each lane (added)
- `project-brain/shared-cache`: A delivery that says that an issue left removes its entry (added)

## Impact

- Code: `src/devops_cli/exceptions/git.py`, `src/devops_cli/github/issue_answer.py` (new), `src/devops_cli/github/client.py`, `src/devops_cli/roadmap/stores/github_store.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_job_phases.py`, `src/devops_cli/roadmap/stage/plan_drift.py`, `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/release_feed.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/server/service.py`, `src/devops_cli/server/routes/webhooks.py`, `src/devops_cli/models/webhooks.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/stores/test_roadmap_github_store_issue_answer.py`, `tests/roadmap/test_roadmap_rows_issue_answer.py`, `tests/roadmap/stage/test_roadmap_stage_prepare.py`, `tests/roadmap/stage/test_roadmap_stage_failure_class.py`, `tests/roadmap/stage/test_roadmap_stage_drift.py`, `tests/roadmap/test_roadmap_release_feed.py`, `tests/github/test_github_client_issue_reads.py`, `tests/server/test_server_service.py`, `tests/server/routes/test_webhooks_brain.py`, `tests/roadmap/stores/test_roadmap_store_contract.py`, the 2 answers of `tests/roadmap/test_roadmap_run_scoped_update.py` that held no `number`, and the fakes `GitHubFake` (`move_issue` with `followed`, `delete_issue`, `rename_repository`), `RunnerSession` (404, 410 and 301) and `InMemoryRoadmapStore` (the error class)
- Documents: `docs/CLUSTER.md`, `docs/ERRORS.md` (generated)
- GitHub requests: a 404, 410 or 301 of a listing below a number costs one read of the issue. The first answer with a requested number and another repository name costs one read of the repository in the life of the reader. No other read is added. A delivery that says that an issue left costs no request.
- Stage Job: an active change folder whose issue is no issue of the repository names no open plan and gives no record in the issue listing of the agent. The Job goes on with its item.
- Deleted internal code: `_repository_named`, `_rest_repository` and `_page_repository` of `github_store.py` move to `issue_answer.py`. No other code is deleted.

## Feasibility

- GitHub documents the statuses. The REST reference of "Get an issue" (`docs.github.com/en/rest/issues/issues`, read on 2026-11-26) lists 200, 301, 304, 404 and 410, and says: "The API returns a 301 Moved Permanently status if the issue was transferred to another repository." and "If the issue was deleted from a repository where the authenticated user has read access, the API returns a 410 Gone status."
- GitHub documents the event. "Webhook events and payloads", event `issues` (read on 2026-11-26), lists the action types `transferred` ("An issue was transferred to another repository.") and `deleted` ("An issue was deleted."). Each payload holds `issue`, and the common fields `action`, `repository` and `sender`. The page gives no form for the fields of `changes` of `transferred`, so the change reads none of them: `GitHubWebhookPayload` reads `action`, `repository.full_name`, `repository.private` and `issue.number` already.
- The defect is in the source at the base commit `8c485655e`. `_revalidate_issue` and `_read_or_none` take only `HTTPStatus.NOT_FOUND` as absent. `comments_on`, `label_changes` and `blocked_by` call `_listing` and no `_gone`. `plan_alternatives` and `write_each` have no branch for a number that is no issue.
- The read of the stage Job is in the source. `_decide` of `src/devops_cli/roadmap/stage/stage_job_phases.py` calls `open_plan_creates`, which calls `store.item(number)` for each active change folder (`src/devops_cli/roadmap/planned.py`), and `issue_listing` calls `store.item(number)` for each active folder whose issue is no open item. Both take None as no open plan.
- The new tests fail on the base: `uv run devops ci fail-to-pass --base origin/main` at the base commit `8c485655e` gave 39 failed on the base and 338 passed in the 10 changed test modules, and exit status 0. The case of a stage Job with an active change folder whose issue answers 301 fails there. The same case with the issue at its new place passes there, because #7331 refuses that answer.
- The set of the rows is the 14 rows of `STATUS_LANE_ROWS`, `TRIAGE_LANE_ROWS` and `MODEL_LANE_ROWS` (`src/devops_cli/roadmap/run.py`). The design lists what each row does for such an item, and the rows that this change leaves as they are.

## Existing Tool Considered

The need is a rule of the store and of the rows of this project. No library holds it. The change uses what the project has: `http.HTTPStatus` for the statuses, `gh_http_status` for the status of a failed `gh` command, `RepoRef` for the comparison of repository names, and the comparison of #7331, which moves to one module and gets two more callers. Cost to build: about 250 lines of source and 30 test cases, about 600 thousand tokens and 6 hours. Deleted internal code: none.
