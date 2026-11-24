# Tasks

## 1. Subscribe the roadmap consumer to the release event

Kind: behavior. Reads: `src/devops_cli/config/constants.py`, `src/devops_cli/github/onboard/service_rows.py`, `docs/CLUSTER.md`, `tests/server/test_server_service.py`, `tests/roadmap/test_roadmap_run_due_table.py`. Changes: `src/devops_cli/config/constants.py`, `docs/CLUSTER.md`, `tests/server/test_server_service.py`, `tests/roadmap/test_roadmap_run_due_table.py`.
Adds: `CONST_ROADMAP_RELEASE_WEBHOOK_EVENTS`

- [ ] 1.1 Extend the failing `test_the_event_set_and_step_8_name_the_same_events` in `tests/server/test_server_service.py` and `test_the_table_runs_the_lanes_in_order_and_names_no_release_job` in `tests/roadmap/test_roadmap_run_due_table.py` for the scenarios `The event set holds the pull, review, check and release events` and `The runbook step and the event set name the same events`: the sorted list is `check_suite`, `issue_comment`, `issues`, `pull_request`, `pull_request_review` and `release`, and step 8 of `docs/CLUSTER.md` names each event of the set. Drop the case `("release", _event_payload("published")),` of `test_an_event_no_consumer_subscribes_to_gets_no_subscriber_and_starts_no_round`, which the subscription makes false, and drop the words `GitHub Releases` from its docstring
  - Verification: `$ uv run devops ci test tests/server/test_server_service.py tests/roadmap/test_roadmap_run_due_table.py tests/roadmap/test_roadmap_run_webhook_keys.py` fails on the base
- [ ] 1.2 Add `CONST_ROADMAP_RELEASE_WEBHOOK_EVENTS: Final[frozenset[str]] = frozenset({"release"})` beside the comment event set of `src/devops_cli/config/constants.py` and union it into `CONST_ROADMAP_WEBHOOK_EVENTS` there, leaving `CONST_ROADMAP_INTAKE_BATCH_KEYS` unchanged. Add `release` to the event list of step 8 of `docs/CLUSTER.md`, make the sorted event list of `tests/roadmap/test_roadmap_run_due_table.py` hold the six events, and make the same list of `test_the_event_set_and_step_8_name_the_same_events` in `tests/server/test_server_service.py` hold them. Drop the `release` case of `test_an_event_no_consumer_subscribes_to_gets_no_subscriber_and_starts_no_round`, which the subscription makes false. The onboard row requires and writes each event of the constant through `_sends_events` of `src/devops_cli/github/onboard/service_rows.py`, so the `release` event reaches each hook with no edit there
  - Verification: `$ uv run devops ci test tests/server/test_server_service.py tests/roadmap/test_roadmap_run_due_table.py tests/roadmap/test_roadmap_run_webhook_keys.py` passes
- [ ] 1.3 Edit step 8 of `docs/CLUSTER.md` to name the `release` event beside the five events that the consumer takes
  - Verification: `$ uv run devops ci docs` passes

## 2. Parse the release object of a webhook payload

Kind: behavior. Reads: `src/devops_cli/models/webhooks.py`, `tests/models/test_webhooks.py`. Changes: `src/devops_cli/models/webhooks.py`, `tests/models/test_webhooks.py`.
Adds: `WebhookRelease`

- [ ] 2.1 Write the failing `test_a_published_release_payload_parses` in `tests/models/test_webhooks.py` for the requirement `The payload holds the release fields` and its scenario `A published release payload parses`: a `release` payload with the action `published` and the six release fields validates, and the payload release holds the tag, the URL and the body, with `draft` and `prerelease` false
  - Verification: `$ uv run devops ci test tests/models/test_webhooks.py` fails on the base
- [ ] 2.2 Add `WebhookRelease` beside `WebhookCheckSuite` in `src/devops_cli/models/webhooks.py` with `tag_name: str`, `html_url: str`, `body: str | None = None`, `draft: bool = False`, `prerelease: bool = False` and `published_at: datetime | None = None`, with the model config `ConfigDict(extra="ignore", frozen=True)` that the other payload models carry, and add `release: WebhookRelease | None = None` to `GitHubWebhookPayload` there. `published_at` stays optional, so a delivery of a draft still validates and reaches the refusal instead of answering 400
  - Verification: `$ uv run devops ci test tests/models/test_webhooks.py` passes

## 3. Refuse an unwanted release delivery

Kind: behavior. Reads: `src/devops_cli/server/routes/webhooks.py`, `src/devops_cli/models/webhooks.py`, `src/devops_cli/config/constants.py`, `tests/server/routes/test_roadmap_consumer_comment_events.py`. Changes: `src/devops_cli/server/routes/webhooks.py`, `src/devops_cli/config/constants.py`, `tests/server/routes/test_roadmap_consumer_release_events.py` (new).
Adds: `CONST_SERVICE_STATUS_RELEASE_REFUSED`, `_release_refusal`

- [ ] 3.1 Write the failing `test_an_unwanted_release_is_refused_with_no_request` in `tests/server/routes/test_roadmap_consumer_release_events.py` for the requirement `The consumer refuses an unwanted release delivery` and its scenario `An unwanted release is refused`: a signed `release` delivery with the action `created`, one of a draft, one of a prerelease and one whose release holds no publication time are each answered with `CONST_SERVICE_STATUS_RELEASE_REFUSED`, queue no round and no scoped update, and the fake GitHub client records no request; a signed `release` delivery whose payload holds no `release` object is not refused. The module builds its own signed delivery helper, as `tests/server/routes/test_roadmap_consumer_comment_events.py` does
  - Verification: `$ uv run devops ci test tests/server/routes/test_roadmap_consumer_release_events.py` fails on the base
- [ ] 3.2 Add `CONST_SERVICE_STATUS_RELEASE_REFUSED: Final[str] = "ignored_release_refused"` beside the comment refusal statuses in `src/devops_cli/config/constants.py`. In `roadmap_consumer` of `src/devops_cli/server/routes/webhooks.py` add the nested `_release_refusal(payload)` that answers that status when the payload carries a release whose action is not `published`, whose `draft` is true, whose `prerelease` is true or whose `published_at` is None, and that answers nothing when `payload.release` is absent, and extend the nested `refuse_comment` there to `return refuse_own_write(payload) or _comment_refusal(payload, payload.comment) or _release_refusal(payload)`. The refusal stays wired as the `refusal` of the returned `WebhookConsumer`, so it runs before `deliver` and before any GitHub request, and `_REFUSAL_OUTCOMES` counts the new status as ignored with no other change
  - Verification: `$ uv run devops ci test tests/server/routes/test_roadmap_consumer_release_events.py` passes

## 4. Run the release comments row scoped to a published release

Kind: behavior. Reads: `src/devops_cli/roadmap/release_comments.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/roadmap/release_feed.py`, `tests/roadmap/test_roadmap_release_comments.py`, `tests/roadmap/test_roadmap_run_scoped_update.py`. Changes: `src/devops_cli/roadmap/release_comments.py`, `src/devops_cli/roadmap/run.py`, `tests/roadmap/test_roadmap_release_comments.py`, `tests/roadmap/test_roadmap_run_scoped_update.py`.
Adds: `comment_one_release`, `_release_one`, `_SCOPED_RELEASE`

- [ ] 4.1 Write the failing `test_one_release_comments_its_closed_issue_once` in `tests/roadmap/test_roadmap_release_comments.py` and the failing `test_a_release_delivery_comments_its_closed_issue_once` in `tests/roadmap/test_roadmap_run_scoped_update.py` for the requirement `A published release delivery comments at once` and its scenarios `The scoped update comments the closed issue`, `A second delivery posts no comment` and `The scoped update posts only the released marker`, and for the requirement `The Service runs a subscribed event's scoped update on the lane of its table row`: the scoped update posts one `released` marker on issue 123 of the tag `v1.2.3` and sets its flag in the ledger `release_comments.json`, a second delivery posts none, no `live` marker appears, the map `SCOPED_UPDATES` holds `("release", "published")` with the job `release_comments`, and the cases of `comment_releases` keep passing
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_release_comments.py tests/roadmap/test_roadmap_run_scoped_update.py` fails on the base
- [ ] 4.2 Add `comment_one_release(store, feed, release, *, ledger_path)` to `src/devops_cli/roadmap/release_comments.py`: it reads `ReleaseLedger`, posts `released_body` once on each number of `closed_issues` through `_comment_once` with `marker`, sets the `released` flag of the tag, writes the ledger `release_comments.json` in a `finally`, and posts no `live` marker. Add `release: WebhookRelease | None = None` to `WebhookDelivery` in `src/devops_cli/roadmap/run.py` and import `WebhookRelease` from `devops_cli.models.webhooks` at the top of that module. Add `_release_one(store, delivery, *, repo_dir, now)` beside `_watch_one` there: it returns an empty `JobOutcome` when the delivery carries no release, builds the record `ReleaseInfo` of `src/devops_cli/roadmap/release_feed.py` from the release, and calls `comment_one_release` with a `GitHubReleaseFeed` built from `delivery.repo` and the ledger path `repo_dir / CONST_ROADMAP_RELEASE_LEDGER_FILENAME`, as `_run_release_comments_adapter` does. Add `_SCOPED_RELEASE = ScopedUpdate(job="release_comments", runner=_release_one)` beside the watch entry and the key `("release", "published")` to the map `SCOPED_UPDATES` of that module. The update needs no clone, and `run_scoped_update` runs it on the lane of the row. The 11-minute round of the `release_comments` row and its `Live since` pass stay as they are
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_release_comments.py tests/roadmap/test_roadmap_run_scoped_update.py` passes

## 5. Run the scoped release update on a published delivery

Kind: behavior. Reads: `src/devops_cli/server/routes/webhooks.py`, `src/devops_cli/roadmap/run.py`, `docs/CLUSTER.md`, `tests/server/routes/test_roadmap_consumer_comment_events.py`, `tests/server/routes/test_roadmap_consumer_pull_events.py`, `tests/server/test_server_service.py`, `tests/models/test_webhooks.py`, `tests/server/routes/test_k8s_roadmap_service.py`, `tests/server/test_mattermost_slash_command.py`, `tests/telemetry/test_service_counter_series.py`. Changes: `src/devops_cli/server/routes/webhooks.py`, `tests/server/routes/test_roadmap_consumer_release_events.py`, `docs/CLUSTER.md`.

- [ ] 5.1 Write the failing `test_a_published_release_delivery_runs_the_scoped_release_update` and `test_a_release_delivery_with_no_release_keeps_a_whole_round_hint` in `tests/server/routes/test_roadmap_consumer_release_events.py` for the requirement `The Service runs a subscribed event's scoped update on the lane of its table row` and its scenario `An unscopeable event keeps a whole-round hint`: a signed `release` `published` delivery that carries a release queues one scoped update on the lane `release_comments` and no whole round, and a signed `release` `published` delivery whose payload holds no `release` object queues a trigger on each lane and no scoped update
  - Verification: `$ uv run devops ci test tests/server/routes/test_roadmap_consumer_release_events.py` fails on the base
- [ ] 5.2 Read the release of the payload in `deliver` of `src/devops_cli/server/routes/webhooks.py` and pass it as `release=release` to `WebhookDelivery(...)`, so the delivery carries the release of a `release` event. Gate the scoped branch of `deliver` on the delivery instead of on the subject alone: `if scoped is not None and (subject is not None or delivery.release is not None):`, so a published release delivery, which names no issue number and no pull request number, runs its scoped update at once instead of staying a whole-round hint. The subject of the trigger stays an issue number and is absent for a release delivery, so `service_manager.enqueue_trigger` takes its default subject and no tag is put in it. The wake of the other lanes is unchanged
  - Verification: `$ uv run devops ci test tests/server/routes/test_roadmap_consumer_release_events.py` passes
- [ ] 5.3 Edit step 20 of `docs/CLUSTER.md` to say that a published `release` delivery runs its `Released in` pass at once on the lane of the row, that a draft, a prerelease, another action and a release with no publication time are refused, and that the 11-minute round stays for `Live since` and reconciliation. Update `tests/roadmap/test_roadmap_limit_classes.py`
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1: `CONST_ROADMAP_WEBHOOK_EVENTS` includes `"release"`, and `k8s/README.md` step 8 lists `"release"`.
- Group 3: Draft releases, prereleases, and `release` actions other than `"published"` are ignored at payload refusal with zero GitHub API requests.
- Group 5: A `release` `published` webhook runs a scoped `status` update that posts `Released in <tag>` and updates `release_comments.json`.
- Group 4: The 11-minute `release_comments` poll continues to reconcile missed webhooks and post `Live since <time>` after cluster rollout.
- Group 5: Offline unit tests cover payload validation, draft/prerelease refusal, and scoped `Released in <tag>` commenting.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
