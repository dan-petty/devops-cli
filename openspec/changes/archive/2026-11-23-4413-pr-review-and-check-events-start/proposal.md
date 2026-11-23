# Proposal

## Why

The roadmap Service takes only the `issues` webhook event (#4413), so a new head, a review or a finished check suite waits for the next poll of the `watch` row, and each round reads every open pull request of the repository.

## What Changes

- `CONST_ROADMAP_WEBHOOK_EVENTS` holds `pull_request`, `pull_request_review` and `check_suite` beside the `issues` events, and step 8 of the roadmap-service runbook names the same four events.
- `WebhookPullRequest`, `WebhookCheckSuite` and `delivery_numbers` give a delivery the pull request numbers that it names, and `issue` stays optional.
- `watch_round` takes the pull request numbers of a delivery and reads only the pull requests that the store or the watch ledger records.
- `SCOPED_UPDATES` routes each pull request, review and check suite action to the watch row, scoped to the delivered numbers.
- `roadmap_consumer` reads the numbers from the payload, refuses the App's own deliveries, and keeps the whole-round hint for an event with no row.
- The poll of the `watch` row stays the reconciling path, and a scoped update writes no job's last success.
- Offline tests cover the payloads, the routing and the scoped round.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-service-webhooks`: The consumer takes the pull request, review and check events
- `roadmap-scoped-updates`: A pull request, review or check suite delivery runs the watch row scoped to its pull requests, An event with no scoped update stays a hint, The Service runs a subscribed event's scoped update on the lane of its table row
- `roadmap-watch-row`: A scoped watch round reads only the delivered pull requests, Watch reads open roadmap pull requests with one GraphQL query

## Impact

- Code: `src/devops_cli/config/constants.py`, `src/devops_cli/models/webhooks.py`, `src/devops_cli/roadmap/watch_row.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/server/routes/webhooks.py`
- Documents: `docs/CLUSTER.md`
- Tests: `tests/roadmap/test_roadmap_run_due_table.py`, `tests/server/test_server_service.py`, `tests/models/test_webhooks.py`, `tests/roadmap/test_roadmap_watch_scoped.py`, `tests/roadmap/test_roadmap_run_scoped_update.py`, `tests/server/routes/test_roadmap_consumer_pull_events.py`

## Feasibility

- The `probes` line confirms the readiness row module path that the issue cites: The path `src/devops_cli/roadmap/stage/stage_ready.py` is a file of the staging commit, and `read_file` of it showed `The stage job opens a draft pull request for each item, and its plan is complete when it opens it.`
- The `probes` line confirms the constant path that the issue cites: The path `src/devops_cli/config/constants.py` is a file of the staging commit, and `read_file` of lines 4004 to 4010 showed the event set built from `CONST_ROADMAP_INTAKE_BATCH_KEYS`, at `src/devops_cli/config/constants.py:4005:# takes (#1386): the issues events only.` and `src/devops_cli/config/constants.py:4006:CONST_ROADMAP_WEBHOOK_EVENTS: Final[frozenset[str]] = frozenset(`.
- The `probes` line confirms the payload model path that the issue cites: The path `src/devops_cli/models/webhooks.py` is a file of the staging commit, and `read_file` of it showed `class GitHubWebhookPayload(BaseModel):` with `issue: WebhookIssue | None = None`.
- The `probes` line confirms the routing path that the issue cites: The path `src/devops_cli/roadmap/run.py` is a file of the staging commit, and `read_file` of lines 1259 to 1273 showed `SCOPED_UPDATES: Mapping[tuple[str, str], ScopedUpdate] = MappingProxyType(`.
- The `probes` line shows that `stage.pr` is a job-record key and no path: The path `stage.pr` is no file of the staging commit. No commit in the history deleted or renamed it.
- The `probes` line names the two files that a bare `models/webhooks.py` can mean: The path `models/webhooks.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/models/webhooks.py`, which holds `class GitHubWebhookPayload(BaseModel):`, and `src/devops_cli/server/routes/webhooks.py`, which holds `def roadmap_consumer(service_manager: ServiceManager) -> WebhookConsumer:`. No commit in the history deleted or renamed it. The plan cites `src/devops_cli/models/webhooks.py` for the payloads.
- `read_file` of `src/devops_cli/config/constants.py`, lines 3984 to 3988, showed the intake keys are the `issues` events only, `CONST_ROADMAP_INTAKE_BATCH_KEYS`, at `src/devops_cli/config/constants.py:3985:("webhook", "issues", "opened"),`.
- `read_file` of `src/devops_cli/models/webhooks.py` showed a payload of `action`, `repository`, `sender` and `issue` only, with the issue optional at `src/devops_cli/models/webhooks.py:53:issue: WebhookIssue | None = None`, and the model at `src/devops_cli/models/webhooks.py:43:class GitHubWebhookPayload(BaseModel):`.
- `read_file` of `src/devops_cli/server/routes/webhooks.py`, lines 270 to 341, showed the consumer scopes a delivery by its issue number alone at `src/devops_cli/server/routes/webhooks.py:298:subject = payload.issue.number if payload is not None and payload.issue else None`, the set it takes, `events=CONST_ROADMAP_WEBHOOK_EVENTS,`, at `src/devops_cli/server/routes/webhooks.py:338:events=CONST_ROADMAP_WEBHOOK_EVENTS,`, the refusal of the App's own deliveries at `src/devops_cli/server/routes/webhooks.py:330:def refuse_own_write(payload: GitHubWebhookPayload) -> str | None:`, and the scoped path at `src/devops_cli/server/routes/webhooks.py:323:if service_manager.enqueue_scoped(repo, lane, run_scoped):`.
- `read_file` of `src/devops_cli/roadmap/run.py`, lines 1259 to 1273, showed one scoped row only, `_SCOPED_INTAKE = ScopedUpdate(job="intake", runner=_intake_one)`, and the table at `src/devops_cli/roadmap/run.py:1271:SCOPED_UPDATES: Mapping[tuple[str, str], ScopedUpdate] = MappingProxyType(`.
- `read_file` of `src/devops_cli/roadmap/run.py`, lines 667 to 676, showed a delivery record that requires one issue number, `number: int`, in the class at `src/devops_cli/roadmap/run.py:668:class WebhookDelivery:`.
- `read_file` of `src/devops_cli/roadmap/run.py`, lines 1068 to 1096, showed the status lane holds the row `watch` with `STATUS_LANE_ROWS: tuple[JobRow, ...] = (`, at `src/devops_cli/roadmap/run.py:1092:name="watch",` and `src/devops_cli/roadmap/run.py:1093:interval=timedelta(minutes=DEFAULT_ROADMAP_WATCH_INTERVAL_MINUTES),`.
- `search_code` for `DEFAULT_ROADMAP_WATCH_INTERVAL_MINUTES: int` gave the staged value `src/devops_cli/config/defaults.py:1231:DEFAULT_ROADMAP_WATCH_INTERVAL_MINUTES: int = 3`, the interval of the watch row.
- The status lane no longer holds a `stage_ready` row: it holds the row `watch` at `src/devops_cli/roadmap/run.py:1092:name="watch",`, and `search_code` for `DEFAULT_ROADMAP_STAGE_READY_INTERVAL_MINUTES` gave only archived change files and the retired-name list at `tests/roadmap/test_roadmap_limit_classes.py:88:"DEFAULT_ROADMAP_STAGE_READY_INTERVAL_MINUTES",` under `tests/roadmap/test_roadmap_limit_classes.py:87:# Replaced by DEFAULT_ROADMAP_WATCH_INTERVAL_MINUTES (#5024)`.
- The owner decision of 2026-11-13 in the issue body replaces the scoped `stage_ready` with a scoped sweep of the delivered pull request, so the plan builds the watch-row sweep and no code for the retired row.
- The setup step that the issue calls step 8 of `k8s/README.md` is step 8 of the roadmap-service runbook: `search_code` for `Add each repo's webhook` gave one hit, `docs/CLUSTER.md:47:8. Add each repo's webhook:`, and `search_code` for `Issues event` gave no hit in `k8s/README.md`.
- `read_file` of `src/devops_cli/roadmap/watch_row.py`, lines 750 to 800, showed `_collect_rest_candidates` builds its candidates from the `stage.pr` record at `src/devops_cli/roadmap/watch_row.py:763:rec = item.job_record.get(StageRecordKey.PR)`.
- `read_file` of `src/devops_cli/roadmap/watch_row.py`, lines 856 to 900, showed a poll round reads every open pull request with one GraphQL query, `graphql_nodes = _read_open_pulls_graphql(owner, name)`, at `src/devops_cli/roadmap/watch_row.py:893:graphql_nodes = _read_open_pulls_graphql(owner, name)`.
- The two tests that the change updates are known: `tests/server/test_server_service.py:1882:("pull_request", _event_payload("closed")),` expects `no_subscriber` for an event that the consumer now takes, and `tests/roadmap/test_roadmap_run_scoped_update.py:111:pull = run(webhook_delivery("opened", placed, event="pull_request"))` expects None for a delivery that now has a row.
- The due-table case names the set as `tests/roadmap/test_roadmap_run_due_table.py:131:["issues"],`, so the group that adds the events updates that case, and it updates the mapping case at `tests/roadmap/test_roadmap_run_scoped_update.py:54:def test_the_issues_actions_run_a_scoped_intake_on_the_lane_of_intake() -> None:` and the case at `tests/roadmap/test_roadmap_run_scoped_update.py:96:def test_an_edit_of_an_item_and_an_event_with_no_scoped_update_change_nothing(`.
- `read_spec` of `roadmap-scoped-updates` gave the requirement `An event with no scoped update stays a hint` with the one scenario `A closed issue and an opened pull request`, and gave `The Service runs a subscribed event's scoped update on the lane of its table row` with the scenarios `A subscribed issues delivery runs on the triage lane` and `An unscopeable event keeps a whole-round hint`; `read_spec` of `roadmap-watch-row` gave `Watch reads open roadmap pull requests with one GraphQL query` with the scenario `Open pull requests read via GraphQL`; `read_spec` of `roadmap-service-webhooks` listed no requirement named `The consumer takes the pull request, review and check events`.
- `list_files` of `tests/models` and of `tests/server/routes` showed both folders exist, so the two new test modules sit in the folder that mirrors the package of the code that they test, and `list_files` of `tests/roadmap` showed `tests/roadmap/test_roadmap_watch_row.py` and `tests/roadmap/test_roadmap_run_scoped_update.py` exist.
- `watch_round` needs a client of the GitHub service and a network for `get_pull_status` and `read_check_runs`, and no checkout of the repository.
- `run_scoped_update` needs a client of the GitHub service and a network through the runner that it calls, and no checkout; it reads the state file beside `schedule.json`.
- `roadmap_consumer`'s `deliver` needs a client of the GitHub service and a network for the scoped update that it queues, and no checkout of the repository.
- `_intake_one` needs a client of the model gateway and no checkout; `delivery_numbers` needs no checkout, no client and no network.
- Each verify command is `uv run devops ci test` with a test path, so `uv` and `pytest` come from the runner image, no program is `NOT_IN_RUNNER`, and the pod settings `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, `capabilities.drop: ALL` and `seccompProfile: RuntimeDefault` apply; the tests write only under the pytest temporary directory.
- The failure classes that the plan needs are `test` for a failing test, and `lint` and `types` for the static checks of the same files; no command of the plan reaches a cluster, a real scanner or a network.
- The first checks that the implementation runs against the real system are, in the order of the groups, `uv run devops ci test tests/roadmap/test_roadmap_run_due_table.py tests/server/test_server_service.py`, `uv run devops ci test tests/models/test_webhooks.py`, `uv run devops ci test tests/roadmap/test_roadmap_watch_scoped.py`, `uv run devops ci test tests/roadmap/test_roadmap_run_scoped_update.py` and `uv run devops ci test tests/server/routes/test_roadmap_consumer_pull_events.py`.
- The live proof of the owner decision is a person's step after the merge, the release and the App subscription: a check end on an open bot pull request makes a watch result line within 2 minutes, and a comment gives the delivery id and the result line; the plan runs no such check.

## Existing Tool Considered

gidgethub and githubkit verify and parse GitHub webhook payloads into typed models, but neither narrows the watch row to the delivered pull request numbers nor reads the stage records of an item. The change builds its own code at about 110k tokens to build, keep and fix, and 2.5 hours of elapsed time, and it deletes no internal code.

## Dependencies

None.
