# Proposal

## Why

The Service does not subscribe to `issue_comment`, so a person's retry or reply waits for the next poll: the stop pass lists the comments of every Blocked item each round, and refine reads a reply only at its interval (#4415). This change takes a trusted comment as it arrives, refuses every other one before any GitHub request, and runs the row that the comment wakes, scoped to the issue it names.

## What Changes

- `src/devops_cli/models/webhooks.py` gains `WebhookComment` with `body`, `author_association` and `created_at`, a `pull_request` field on `WebhookIssue`, and a `comment` field on `GitHubWebhookPayload`.
- `src/devops_cli/config/constants.py` gains `CONST_ROADMAP_COMMENT_WEBHOOK_EVENTS` and unions it into `CONST_ROADMAP_WEBHOOK_EVENTS`, gains `CONST_SERVICE_STATUS_COMMENT_REFUSED` and `CONST_SERVICE_STATUS_UNTRUSTED_COMMENT`, and leaves `CONST_ROADMAP_INTAKE_BATCH_KEYS` unchanged.
- `roadmap_consumer` refuses an `issue_comment` delivery at `src/devops_cli/server/routes/webhooks.py:158:refusal: Callable[[GitHubWebhookPayload], str | None] = _takes_every_payload` when it is not a created comment, sits on a pull request, comes from a bot, or has an author outside the trusted set, before any GitHub request.
- `scoped_update_of` in `src/devops_cli/roadmap/run.py` gives the `implement` row for a retry comment and the `refine` row for another comment, and `run_scoped_update` takes its row from it, so a comment never queues a whole round.
- `_refine_one` and `_implement_one` run their row on the checkout of its lane, and `comment_asks_retry` gives the retry text that both the route and `retry_asked` read.
- Step 8 of `docs/CLUSTER.md` names `issue_comment` with the other four events, step 11 no longer says that the Service takes no comment event, and the webhook tests cover each refusal and both routes offline.
- The two cases that expected `issue_comment` to reach no subscriber now expect the accepted comment delivery, and the two sorted event lists gain `issue_comment`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-service-webhooks`: The payload holds the comment and the pull request marker, The consumer refuses a comment it does not trust, The consumer takes the pull request, review and check events
- `roadmap-scoped-updates`: An issue comment delivery runs the row that its text wakes, The Service runs a subscribed event's scoped update on the lane of its table row

## Impact

- Code: `src/devops_cli/models/webhooks.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/server/routes/webhooks.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/roadmap/implement/implement.py`
- Documents: `docs/CLUSTER.md`
- Tests: `tests/models/test_webhooks.py`, `tests/server/test_server_service.py`, `tests/roadmap/test_roadmap_run_due_table.py`, `tests/server/routes/test_roadmap_consumer_comment_events.py`, `tests/roadmap/test_roadmap_run_scoped_update.py`

## Feasibility

- Probe line, quoted word for word: The path src/devops_cli/models/webhooks.py is a file of the staging commit, and that file holds `src/devops_cli/models/webhooks.py:60:class GitHubWebhookPayload(BaseModel):`, so the plan edits the file and creates no file.
- Probe line, quoted word for word: `WebhookConsumer` defines the field `refusal` at src/devops_cli/server/routes/webhooks.py:158 — that hook is the place where the comment refusal goes.
- Probe line, quoted word for word: The path `issue.pull_request` is no file of the staging commit. The marker is a payload field that the plan creates, so no cited path or identifier is gone.
- The model review's finding is right, and group 2 now answers it at its place: `tests/server/test_server_service.py:1879:("issue_comment", _event_payload("created")),` sits in the no-subscriber table whose assertion is `tests/server/test_server_service.py:1901:[(200, {"status": "no_subscriber"})] * 2,`, and `tests/server/test_server_service.py:2385:_github_post(client, "issue_comment", _event_payload(), "count-4").status_code,` is counted as a no-subscriber delivery by `tests/server/test_server_service.py:2414:("github", "other", "no_subscriber"): 3.0,`, so both cases fail once the consumer subscribes.
- Group 2 changes `tests/server/test_server_service.py`: the no-subscriber test leaves out the `issue_comment` case and the word "Comments", and changes the counter case to the accepted status 202 with `("github", "issue_comment", "accepted"): 1.0` and `("github", "other", "no_subscriber"): 2.0`, which is the status list `[202, 200, 200, 200, 202, 200, 200, 401, 415, 400, 400, 503]`.
- The counter case stays accepted after the refusal of group 3 and the route of group 5: `_event_payload()` holds no `comment` and no issue number, so `refuse_comment` takes the payload and `deliver` falls to its whole-round hint, because `src/devops_cli/server/routes/webhooks.py:300:numbers = payload.delivery_numbers if payload is not None else ()` gives no subject.
- Group 2 also updates the two sorted event lists that the new event breaks: `tests/server/test_server_service.py:2253:["check_suite", "issues", "pull_request", "pull_request_review"],` and `tests/roadmap/test_roadmap_run_due_table.py:131:["check_suite", "issues", "pull_request", "pull_request_review"],`.
- `tests/telemetry/test_service_counter_series.py:186:for event in (*CONST_ROADMAP_WEBHOOK_EVENTS, CONST_SERVICE_EVENT_OTHER)` derives its expectation from the constant, so the event set needs no edit there; group 2 reads the module and keeps it in its verify command.
- Premise, read in the file: the consumer has the refusal hook `src/devops_cli/server/routes/webhooks.py:158:refusal: Callable[[GitHubWebhookPayload], str | None] = _takes_every_payload`, declared in `src/devops_cli/server/routes/webhooks.py:146:class WebhookConsumer(BaseModel):`.
- The scoped table exists at `src/devops_cli/roadmap/run.py:1317:SCOPED_UPDATES: Mapping[tuple[str, str], ScopedUpdate] = MappingProxyType(`, and its record at `src/devops_cli/roadmap/run.py:1289:class ScopedUpdate:` holds `job` and `runner` only.
- The staged payload model holds no comment and no pull request marker on the issue: `src/devops_cli/models/webhooks.py:32:class WebhookIssue(BaseModel):` ends at `src/devops_cli/models/webhooks.py:40:state_reason: str | None = None`, and `src/devops_cli/models/webhooks.py:60:class GitHubWebhookPayload(BaseModel):` ends at `src/devops_cli/models/webhooks.py:72:check_suite: WebhookCheckSuite | None = None`.
- The line numbers of the issue body are stale and its symbols exist: `src/devops_cli/roadmap/run.py:882:result = run_implement_round(store, repo=repo, source=source)` holds the implement call, `src/devops_cli/roadmap/stop_clear.py:349:retry = retry_asked_on(store, item)` holds the retry rule, and `src/devops_cli/roadmap/refine/refine.py:3978:item_number: int | None = None` holds the one-item read of refine, so no cited path or symbol is gone.
- The event set is derived and the intake keys stay separate: `src/devops_cli/config/constants.py:4026:CONST_ROADMAP_WEBHOOK_EVENTS: Final[frozenset[str]] = frozenset(` unions the `issues` events of `src/devops_cli/config/constants.py:3999:CONST_ROADMAP_INTAKE_BATCH_KEYS: Final[tuple[tuple[str, str, str], ...]] = (` with `src/devops_cli/config/constants.py:4021:CONST_ROADMAP_WATCH_WEBHOOK_EVENTS: Final[frozenset[str]] = frozenset(`, so the plan adds a comment event set to the union and leaves the intake keys alone.
- The scoped row is looked up by event and action at `src/devops_cli/roadmap/run.py:1365:update = SCOPED_UPDATES.get((delivery.event, delivery.action))`, so one table key cannot hold two rows for one event and a comment needs its own row choice.
- The delivery record holds no comment: `src/devops_cli/roadmap/run.py:669:class WebhookDelivery:` carries the repository, the event, the action, the issue number and the pull request numbers, so the plan adds the comment body and its time.
- The refusal runs before the scoped lookup: `src/devops_cli/server/routes/webhooks.py:303:scoped = SCOPED_UPDATES.get((event, action))` sits inside `deliver`, and the consumer wires the refusal at `src/devops_cli/server/routes/webhooks.py:346:refusal=refuse_own_write,` with the own-write rule of `src/devops_cli/server/routes/webhooks.py:336:def refuse_own_write(payload: GitHubWebhookPayload) -> str | None:`.
- A refusal status that the route does not map counts as ignored: `src/devops_cli/server/routes/webhooks.py:568:return _acknowledged(first, _REFUSAL_OUTCOMES.get(first, CONST_SERVICE_OUTCOME_IGNORED))`, and the map holds only the own-write status at `src/devops_cli/server/routes/webhooks.py:69:CONST_SERVICE_STATUS_OWN_WRITE: CONST_SERVICE_OUTCOME_SELF,`.
- The retry rule reads a trusted comment and the retry command: `src/devops_cli/roadmap/implement/implement.py:261:def retry_asked(comments: Sequence[IssueComment]) -> bool:` compares each body at `src/devops_cli/roadmap/implement/implement.py:271:and comment.body.strip().casefold() == CONST_ROADMAP_IMPLEMENT_RETRY_COMMENT` with `src/devops_cli/config/constants.py:3820:CONST_ROADMAP_IMPLEMENT_RETRY_COMMENT: Final[str] = "implement: retry"`, and the stop pass reads it at `src/devops_cli/roadmap/stop_clear.py:349:retry = retry_asked_on(store, item)`.
- The trust rule of a person comment checks the association, the login suffix and the pull request marker: `src/devops_cli/roadmap/trust.py:64:def is_person_comment(comment: IssueComment, actor: str | None) -> bool:` with `src/devops_cli/roadmap/trust.py:31:_BOT_LOGIN_SUFFIX = "[bot]"` and `src/devops_cli/roadmap/trust.py:77:and not comment.on_pull_request`, so the route reuses that rule's facts and not its whole model.
- The idle cost that the issue names is the comment listing of a Blocked stop: `src/devops_cli/roadmap/stop_clear.py:50:**Cost.** A Blocked stop that no rule clears costs one request in the first round of a process:`.
- The staged trusted author set holds 3 associations, `OWNER`, `MEMBER` and `COLLABORATOR`, at `src/devops_cli/config/constants.py:4307:CONST_ROADMAP_TRUSTED_AUTHORS: Final[frozenset[str]] = frozenset(` with `src/devops_cli/config/constants.py:4308:{"OWNER", "MEMBER", "COLLABORATOR"}`; the plan allowlists each of the 3 with the reason that GitHub gives it write access, and restricts every other association.
- The staged interval is 7 minutes at `src/devops_cli/config/defaults.py:979:DEFAULT_ROADMAP_REFINE_INTERVAL_MINUTES: int = 7`, and the 31 minutes of the issue body does not match the staged tree, so the plan relies on the staged interval.
- The refine row reads one item number: `src/devops_cli/roadmap/refine/refine.py:3972:def plan_refine(` takes `src/devops_cli/roadmap/refine/refine.py:3978:item_number: int | None = None`, so a comment runs refine for its issue alone.
- Each lane has its own checkout, from `src/devops_cli/roadmap/run.py:1282:def lane_clone_dirname(lane: str) -> str:` and the lane of a row at `src/devops_cli/roadmap/run.py:1276:def lane_of_row(row: str, groups: Mapping[str, Sequence[str]] | None = None) -> str:`, so the scoped runner takes the checkout of its lane.
- The onboarding step that the issue calls step 8 of `k8s/README.md` is step 8 of the runbook: `search_code` for `Add each repo's webhook` gave one hit, `docs/CLUSTER.md:47:8. Add each repo's webhook:`, which names the four events, and the same step continues that the Service takes these four events, so the plan changes `docs/CLUSTER.md` and no file of `k8s/README.md`.
- Step 11 of the runbook states the fact that the change makes false: `docs/CLUSTER.md:50` holds `The Service takes no `issue_comment` event ([ADR 0009](adr/0009-one-webhook-router-delivers-each-event-to-the-consumers-subscribed-to-it.md)).`, so group 2 removes that sentence.
- A test holds step 8 to the event set: `tests/server/test_server_service.py:2243:def test_the_event_set_and_step_8_name_the_same_events() -> None:` reads step 8 with `tests/server/test_server_service.py:2231:RUNBOOK_STEP_8 = "8. "` and requires each event of the set to be named in it, so the new event fails that test until the step names it.
- The base spec of `roadmap-service-webhooks` holds the requirement that the change makes false: `read_spec` gave `The event set of the roadmap consumer, CONST_ROADMAP_WEBHOOK_EVENTS, SHALL hold issues, pull_request, pull_request_review and check_suite, and step 8 of the roadmap-service runbook, docs/CLUSTER.md, SHALL name the same events`, so the delta modifies that requirement with all 2 of its scenarios and adds no requirement that repeats it.
- `ensure_checkout` (`src/devops_cli/roadmap/run.py:496:def ensure_checkout(`) needs a checkout of the repository and a network.
- `run_scoped_update` (`src/devops_cli/roadmap/run.py:1348:def run_scoped_update(`) needs a client of the GitHub service, which its store reads.
- `plan_refine` (`src/devops_cli/roadmap/refine/refine.py:3972:def plan_refine(`) needs a checkout of the repository, a client of the model service and a network.
- `run_implement_round` (`src/devops_cli/roadmap/run.py:882:result = run_implement_round(store, repo=repo, source=source)`) needs a checkout of the repository, a client of the GitHub service and a client of the Kubernetes API.
- `clear_stops` (`src/devops_cli/roadmap/stop_clear.py:364:def clear_stops(`) needs a client of the GitHub service.
- `retry_asked_on` (`src/devops_cli/roadmap/implement/implement.py:287:def retry_asked_on(store: RoadmapStore, item: Item) -> bool:`) needs a client of the GitHub service, which lists the comments of the issue.
- Each refusal test stays offline: the fake client records its requests, as `tests/server/routes/test_roadmap_consumer_pull_events.py:195:return [request for request in api.requested if f"/pulls/{pull}" in request]` shows, and the fake Service runs a scoped update at once at `tests/server/routes/test_roadmap_consumer_pull_events.py:91:def enqueue_scoped(self, repo: str, lane: str, scoped: Callable[[], None]) -> bool:`.
- The new test module `tests/server/routes/test_roadmap_consumer_comment_events.py` sits beside `tests/server/routes/test_roadmap_consumer_pull_events.py` and builds its own signed delivery helper as `tests/server/routes/test_roadmap_consumer_pull_events.py:178:def _deliver(` does.
- `uv run devops ci test` runs `uv`, `python` and `pytest` from the image in a pod with `readOnlyRootFilesystem: true`, `runAsNonRoot: true` and `capabilities.drop: ALL`; a failure is the class `test`, and the plan introduces no other program and no command.
- The first checks that the implementation runs against the real system are, in the order of the groups: `uv run devops ci test tests/models/test_webhooks.py`, `uv run devops ci test tests/server/test_server_service.py tests/telemetry/test_service_counter_series.py tests/roadmap/test_roadmap_run_due_table.py`, `uv run devops ci test tests/server/routes/test_roadmap_consumer_comment_events.py`, `uv run devops ci test tests/roadmap/test_roadmap_run_scoped_update.py` and `uv run devops ci test tests/server/routes/test_roadmap_consumer_comment_events.py`.

## Existing Tool Considered

gidgethub parses an `issue_comment` payload and dispatches events, but it brings no trust refusal, no roadmap state and no scoped row, so the change builds those parts itself: about 115k tokens to build, keep and fix, and about 2.5 hours of elapsed time.

## Dependencies

- PR #6912 changes `k8s/README.md`, the path that the first acceptance criterion names. This plan changes no file of that path, because step 8 of the onboarding is step 8 of `docs/CLUSTER.md` at the staged commit, so the two pull requests share no file and neither waits for the other.
