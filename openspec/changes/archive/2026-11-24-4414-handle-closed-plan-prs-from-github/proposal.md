# Proposal

## Why

The Service does not react to the GitHub `pull_request` `closed` event of a staged plan pull request (#4414). A merged plan waits up to 7 minutes for the implement row to set `status/planned` and submit the runner Job, and a plan closed with no merge waits up to 37 minutes for the stage row to record the rejection. The delivery already reaches the Service and runs the scoped watch round, so the two rows need the key that makes them due and a wake of their lanes.

## What Changes

- `src/devops_cli/config/constants.py:4014:CONST_ROADMAP_STAGE_BATCH_KEYS: Final[tuple[tuple[str, str, str], ...]] = (` gains the key `("webhook", "pull_request", "closed")`, so a closed plan pull request makes the `stage` and `implement` rows due at once.
- `scoped_update_wakes_lanes` returns True for a `pull_request` `closed` delivery at `src/devops_cli/roadmap/run.py:1332:return delivery.action == "edited" or (outcome is not None and outcome.placed_critical_or_p0)`, so the consumer wakes the lanes of the two rows instead of waiting for their intervals.
- `tests/roadmap/test_roadmap_run_webhook_keys.py:41:def test_an_issues_key_makes_due_only_the_rows_that_declare_it(` gains a neighbour test for the closed key and a test that the closed delivery wakes the other lanes.
- A new test module `tests/roadmap/test_roadmap_closed_plan_webhook.py` covers the merged plan, the rejected plan and a number that no open item records, with no model request.
- `docs/CLUSTER.md:47:A label change or a close makes` and the `all` stack row of `k8s/README.md` name the new key and the two outcomes.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-scoped-updates`: A closed plan pull request wakes the lanes of its rows, A webhook key makes only the rows that declare it due

## Impact

- Code: `src/devops_cli/config/constants.py`, `src/devops_cli/roadmap/run.py`
- Documents: `docs/CLUSTER.md`, `k8s/README.md`
- Tests: `tests/roadmap/test_roadmap_run_webhook_keys.py`, `tests/roadmap/test_roadmap_closed_plan_webhook.py`

## Feasibility

- Probe line, word for word: "The path `implement_submit.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/implement/implement_submit.py`. No commit in the history deleted or renamed it." That module defines `def run_implement_round(` and runs `swept = sync_statuses(store, repo=repo, planned=planned).failed` at `src/devops_cli/roadmap/implement/implement_submit.py:725:swept = sync_statuses(store, repo=repo, planned=planned).failed`, so the cited name is a package file of the staged tree and no cited path is a false premise.
- Probe line, word for word: "The path `status_sync.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/status_sync.py`. No commit in the history deleted or renamed it." That module defines `def sync_statuses(store: RoadmapStore, *, repo: str, planned: PlannedChanges) -> StatusSynced:` at `src/devops_cli/roadmap/status_sync.py:246:def sync_statuses(store: RoadmapStore, *, repo: str, planned: PlannedChanges) -> StatusSynced:`, and its `return CONST_ROADMAP_STATUS_PLANNED if facts.plan_merged else CONST_ROADMAP_STATUS_READY` at `src/devops_cli/roadmap/status_sync.py:117:return CONST_ROADMAP_STATUS_PLANNED if facts.plan_merged else CONST_ROADMAP_STATUS_READY` gives a merged plan `status/planned`.
- Probe line, word for word: "The path `stage_rejected.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/stage/stage_rejected.py`. No commit in the history deleted or renamed it." That module holds `def reason_comment(` at `src/devops_cli/roadmap/stage/stage_rejected.py:103:def reason_comment(` for the trusted reason and `def comment_text(pull: int, reason: IssueComment | None) -> str:` at `src/devops_cli/roadmap/stage/stage_rejected.py:132:def comment_text(pull: int, reason: IssueComment | None) -> str:` for the comment text, so each cited path is a package file of the staged tree.
- Probe line, word for word: "Not probed, the bound of 10 commands is reached: `src/devops_cli/server/routes/webhooks.py`, `src/devops_cli/roadmap/run.py`, `stage.pr`, `stage.rejected`, `k8s/README.md`, `AGENTS.md`, `tests/roadmap/test_roadmap_run_webhook_keys.py`, `payload.issue`, `src/devops_cli/models/webhooks.py`, `src/devops_cli/roadmap/implement/implement_submit.py`, `src/devops_cli/k8s/cluster_job_api.py`, `src/devops_cli/roadmap/stage/stage_rejected.py`, `src/devops_cli/roadmap/stage/stage_submit.py`, `docs/adr/0017-each-subscribed-webhook-event-runs-the-update-scoped-to-it.md`, `docs/adr/0021-the-roadmap-service-is-a-webhook-router-cluster-pods-run-the-roadmap-jobs-and-valkey-holds-their-shared-state.md`, `docs/CLUSTER.md`, `CONTEXT.md`, `docs/ROADMAP_WORKFLOW.md`, `and.proposal`, `row.clone`, `pull_request`, `closed`, `stage`, `CONST_ROADMAP_WEBHOOK_EVENTS`, `number`, `state`, `merged`, `closed_at`, `GitHubWebhookPayload`, `True`, `status`, `sync_statuses`, `run_implement_round`, `False`, `stage_ready`, `gidgethub`, `ClusterJobs`, `implement`, `DEFAULT_DUE_TABLE`, `batch_keys`, `WebhookPullRequest`". So `pull_request`, `merged` and `closed_at` are `not checked` by the probes; the `read_file` and `search_code` lines below are the evidence for them.
- `read_file` of `src/devops_cli/config/constants.py` lines 4014 to 4018 gives the value of `CONST_ROADMAP_STAGE_BATCH_KEYS`: `("webhook", "issues", "labeled")`, `("webhook", "issues", "unlabeled")` and `("webhook", "issues", "closed")` alone, so a closed plan pull request makes neither the `stage` nor the `implement` row due at this commit.
- `read_file` of `src/devops_cli/config/constants.py` lines 4021 to 4033 gives `CONST_ROADMAP_WATCH_WEBHOOK_EVENTS` as `{"pull_request", "pull_request_review", "check_suite"}` and `CONST_ROADMAP_WEBHOOK_EVENTS` as the union of the webhook intake keys with it, so the event is subscribed already and no repository hook changes.
- Both rows name that one constant: `src/devops_cli/roadmap/run.py:1108:batch_keys=CONST_ROADMAP_STAGE_BATCH_KEYS,` for `implement` and `src/devops_cli/roadmap/run.py:1129:batch_keys=CONST_ROADMAP_STAGE_BATCH_KEYS,` for `stage`, so one edit reaches both rows.
- A due row reads its keys here: `src/devops_cli/roadmap/run.py:1456:return any(key in batch_counts for key in row.batch_keys)`, so the due logic needs no change.
- The delivery names its pull request, so the consumer has a subject: `src/devops_cli/models/webhooks.py:80:if self.pull_request is not None and self.pull_request.number is not None:` and `src/devops_cli/server/routes/webhooks.py:302:subject = issue if issue is not None else next(iter(numbers), None)`.
- The closed action already runs the scoped watch update, and the consumer returns before the whole-round trigger: `src/devops_cli/roadmap/run.py:1307:("pull_request", "closed"),` is in the scoped watch actions, `src/devops_cli/roadmap/run.py:1315:_SCOPED_WATCH = ScopedUpdate(job="watch", runner=_watch_one)` maps it to the watch row, and `src/devops_cli/server/routes/webhooks.py:329:if service_manager.enqueue_scoped(repo, lane, run_scoped):` returns on its success.
- The wake is one predicate and one lane rule: `src/devops_cli/roadmap/run.py:1332:return delivery.action == "edited" or (outcome is not None and outcome.placed_critical_or_p0)` and `src/devops_cli/roadmap/run.py:1345:return tuple(lane for lane in lanes if lane != own or shared)`, and the router already calls the predicate at `src/devops_cli/server/routes/webhooks.py:317:if scoped_update_wakes_lanes(delivery, outcome):`, so the router needs no edit.
- The due table holds 14 rows: `src/devops_cli/roadmap/run.py:1219:DEFAULT_DUE_TABLE: tuple[JobRow, ...] = (*STATUS_LANE_ROWS, *TRIAGE_LANE_ROWS, *MODEL_LANE_ROWS)` joins 9 status rows, 1 triage row and 4 model rows, counted from `read_file` of lines 1097 to 1213, so the new due test decides each of the 14 rows and a row that the key makes due by accident fails it.
- The merged plan is the `implement` row's own work: `src/devops_cli/roadmap/implement/implement_submit.py:721:held = {job.name: job for job in api.list_jobs({CONST_ROADMAP_IMPLEMENT_JOB_LABEL: label})}` lists the running Jobs before the round creates one.
- The unmerged plan is the `stage` row's own work: `src/devops_cli/roadmap/stage/stage.py:3383:rejections = _rejections(store, repo, source, heads, planned, item_number)` and `src/devops_cli/roadmap/stage/stage.py:4222:def _reject_plan(`, which deletes the session-only branch, comments the reason, records the rejection and returns the item to New.
- `read_issue` of #4413 answers "#4413 issue, closed (completed)", and the staged constant holds no `pull_request` key, so the dependency is delivered and the closed plan pull request work of this item remains to be built.
- `find_issues` for "pull_request closed webhook lanes" lists "#5555 open feat(service): webhook events wake the lanes of their jobs", which owns the event-to-lane routing table that this change keeps out of scope.
- The two tests belong in the module that holds them today: `tests/roadmap/test_roadmap_run_webhook_keys.py:41:def test_an_issues_key_makes_due_only_the_rows_that_declare_it(` and `tests/roadmap/test_roadmap_run_webhook_keys.py:74:assert scoped_update_wakes_lanes(webhook_delivery(action, 7), outcome) is wakes`, and the helper exists: `tests/support/roadmap_run.py:585:def webhook_delivery(action: str, number: int, *, event: str = "issues") -> WebhookDelivery:`.
- Precondition of the implement round in the new test: a checkout of the repository, a client of the GitHub API and a client of the Kubernetes API, each faked at its edge as `tests/roadmap/implement/test_roadmap_implement_submit.py` does.
- Precondition of the stage round in the new test: a checkout of the repository, which is the clone of the stage lane, and a client of the GitHub API, given by the clone fixture and the fake store of `tests/support/roadmap_run.py`.
- Precondition of `poll_round`, `build_stub_table` and `scoped_update_wakes_lanes` in the two due tests: no checkout, no client and no network, because the tests pass a stub table and these functions read none of the three.
- The plan introduces no verify program and no new tool: each verify runs the existing `uv run devops ci test` row, which runs `pytest` from the runner image, or the existing `uv run devops ci docs` row. Their failure class is the failed test or the stale document, and each row exits non-zero. The pod keeps `readOnlyRootFilesystem` true, `runAsNonRoot` true, `capabilities.drop` ALL and the seccomp profile `RuntimeDefault`, so no new capability is needed.
- The first checks that the implementation runs: `uv run devops ci test tests/roadmap/test_roadmap_run_webhook_keys.py`, then `uv run devops ci test tests/roadmap/test_roadmap_closed_plan_webhook.py`, then `uv run devops ci docs`.

## Existing Tool Considered

gidgethub (Apache-2.0, maintained) is already the project's GitHub client and the alternatives check of the issue records it as in use: it verifies, parses and routes the `pull_request` `closed` delivery, and the router reads its typed payload at `src/devops_cli/server/routes/webhooks.py:270:def roadmap_consumer(service_manager: ServiceManager) -> WebhookConsumer:`. The status sync, the runner Job, the rejection comment and the session branch delete stay project code at `src/devops_cli/roadmap/implement/implement_submit.py:725:swept = sync_statuses(store, repo=repo, planned=planned).failed` and `src/devops_cli/roadmap/stage/stage.py:4222:def _reject_plan(`, so the change adds no library and builds no new parsing code.

## Dependencies

- #4413: it delivered the `pull_request` subscription, the typed payload and the scoped watch round of the `closed` action, and `read_issue` answers that it is closed (completed), so this plan builds on it.
