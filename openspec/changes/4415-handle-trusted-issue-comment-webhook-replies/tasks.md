# Tasks

## 1. Add the comment and pull request fields to the webhook payload

Kind: behavior. Reads: `src/devops_cli/models/webhooks.py`, `tests/models/test_webhooks.py`. Changes: `src/devops_cli/models/webhooks.py`, `tests/models/test_webhooks.py`.
Adds: `WebhookComment`

- [ ] 1.1 `test_an_issue_comment_payload_exposes_the_comment_and_the_pull_request_marker` in `tests/models/test_webhooks.py`, beside `tests/models/test_webhooks.py:8:def test_a_pull_request_and_a_check_suite_payload_validate() -> None:`, for the scenarios `An issue comment payload` and `A payload with no comment`: an `issue_comment` payload holds the comment body, its author association and its time, the issue holds the pull request marker, and an `issues` payload with no comment validates as before
  - Verification: `$ uv run devops ci test tests/models/test_webhooks.py` fails on the base
- [ ] 1.2 Add `WebhookComment` with `body`, `author_association` and `created_at` in `src/devops_cli/models/webhooks.py`, beside `src/devops_cli/models/webhooks.py:24:class WebhookLabel(BaseModel):`, with `extra="ignore"` and frozen as the other models of the file. Add `pull_request: WebhookPullRequest | None = None` to `src/devops_cli/models/webhooks.py:32:class WebhookIssue(BaseModel):` and `comment: WebhookComment | None = None` to `src/devops_cli/models/webhooks.py:60:class GitHubWebhookPayload(BaseModel):`, after `src/devops_cli/models/webhooks.py:72:check_suite: WebhookCheckSuite | None = None`
  - Verification: `$ uv run devops ci test tests/models/test_webhooks.py` passes

## 2. Hold the comment event in the event set and in step 8

Kind: behavior. Reads: `src/devops_cli/config/constants.py`, `docs/CLUSTER.md`, `tests/server/test_server_service.py`, `tests/telemetry/test_service_counter_series.py`, `tests/roadmap/test_roadmap_run_due_table.py`. Changes: `src/devops_cli/config/constants.py`, `docs/CLUSTER.md`, `tests/server/test_server_service.py`, `tests/roadmap/test_roadmap_run_due_table.py`.
Adds: `CONST_ROADMAP_COMMENT_WEBHOOK_EVENTS`, `CONST_SERVICE_STATUS_COMMENT_REFUSED`, `CONST_SERVICE_STATUS_UNTRUSTED_COMMENT`

- [ ] 2.1 `test_the_event_set_and_step_8_name_the_same_events` and `test_every_path_counts_its_delivery_by_provider_event_and_outcome` in `tests/server/test_server_service.py`, `test_the_table_runs_the_lanes_in_order_and_names_no_release_job` in `tests/roadmap/test_roadmap_run_due_table.py`, and the updated case `test_an_event_no_consumer_subscribes_to_gets_no_subscriber_and_starts_no_round`: `CONST_ROADMAP_WEBHOOK_EVENTS` holds `issue_comment` beside the four events, `CONST_ROADMAP_INTAKE_BATCH_KEYS` holds no comment key, step 8 of `docs/CLUSTER.md` names `issue_comment`, the no-subscriber table holds no `issue_comment` case, and the counter counts the comment delivery as accepted with 2 no-subscriber deliveries
  - Verification: `$ uv run devops ci test tests/server/test_server_service.py tests/telemetry/test_service_counter_series.py tests/roadmap/test_roadmap_run_due_table.py` fails on the base
- [ ] 2.2 Add `CONST_ROADMAP_COMMENT_WEBHOOK_EVENTS: Final[frozenset[str]] = frozenset({"issue_comment"})` beside `src/devops_cli/config/constants.py:4021:CONST_ROADMAP_WATCH_WEBHOOK_EVENTS: Final[frozenset[str]] = frozenset(`, union it into `src/devops_cli/config/constants.py:4026:CONST_ROADMAP_WEBHOOK_EVENTS: Final[frozenset[str]] = frozenset(`, add `CONST_SERVICE_STATUS_COMMENT_REFUSED` and `CONST_SERVICE_STATUS_UNTRUSTED_COMMENT` beside `src/devops_cli/config/constants.py:1720:CONST_SERVICE_STATUS_OWN_WRITE: Final[str] = "ignored_own_write"`, and leave `CONST_ROADMAP_INTAKE_BATCH_KEYS` unchanged. In `tests/roadmap/test_roadmap_run_due_table.py`, make the sorted event list `["check_suite", "issue_comment", "issues", "pull_request", "pull_request_review"]`. In `tests/server/test_server_service.py`, make the same list of `test_the_event_set_and_step_8_name_the_same_events`; drop the `issue_comment` case and the word `Comments` from `test_an_event_no_consumer_subscribes_to_gets_no_subscriber_and_starts_no_round`; and in `test_every_path_counts_its_delivery_by_provider_event_and_outcome` give the comment delivery the status 202, add `("github", "issue_comment", "accepted"): 1.0`, and change `("github", "other", "no_subscriber")` to 2.0, because the payload holds no comment and no issue number and the delivery stays a whole-round hint
  - Verification: `$ uv run devops ci test tests/server/test_server_service.py tests/telemetry/test_service_counter_series.py tests/roadmap/test_roadmap_run_due_table.py` passes
- [ ] 2.3 Edit step 8 of `docs/CLUSTER.md` to name `issue_comment` with the other four events and to say that a trusted comment runs the scoped update of its row, and remove from step 11 the sentence that the Service takes no `issue_comment` event
  - Verification: `$ uv run devops ci docs` passes

## 3. Refuse a comment delivery that the Service does not trust

Kind: behavior. Reads: `src/devops_cli/server/routes/webhooks.py`, `src/devops_cli/roadmap/trust.py`, `src/devops_cli/models/webhooks.py`, `tests/server/routes/test_roadmap_consumer_pull_events.py`, `tests/models/test_webhooks.py`, `tests/server/routes/test_k8s_roadmap_service.py`, `tests/server/test_mattermost_slash_command.py`, `tests/server/test_server_service.py`, `tests/telemetry/test_service_counter_series.py`. Changes: `src/devops_cli/server/routes/webhooks.py`, `tests/server/routes/test_roadmap_consumer_comment_events.py` (new).
Adds: `refuse_comment`

- [ ] 3.1 `test_a_bot_an_edited_action_an_untrusted_author_or_a_pull_request_comment_is_refused_with_no_request` in `tests/server/routes/test_roadmap_consumer_comment_events.py`, for the scenarios `A non-created comment`, `A bot comment`, `An untrusted author comment` and `A pull request comment`: a signed comment with action `edited`, with a bot sender, with a pull request marker or with an association outside `CONST_ROADMAP_TRUSTED_AUTHORS` is refused before `deliver`, answering `CONST_SERVICE_STATUS_COMMENT_REFUSED` for the action, the bot and the pull request marker and `CONST_SERVICE_STATUS_UNTRUSTED_COMMENT` for the untrusted author, which counts as `ignored`, and the fake GitHub client records no request
  - Verification: `$ uv run devops ci test tests/server/routes/test_roadmap_consumer_comment_events.py` fails on the base
- [ ] 3.2 Add `refuse_comment` beside `src/devops_cli/server/routes/webhooks.py:336:def refuse_own_write(payload: GitHubWebhookPayload) -> str | None:` in `src/devops_cli/server/routes/webhooks.py` and return it at `src/devops_cli/server/routes/webhooks.py:346:refusal=refuse_own_write,`, so it runs before `deliver`. It answers the own-write status first, returns None when the payload holds no comment, and refuses a comment whose action is not `created`, whose issue carries a pull request marker, or whose sender login is the Service bot or ends with `[bot]`, each with `CONST_SERVICE_STATUS_COMMENT_REFUSED`; an author association outside `CONST_ROADMAP_TRUSTED_AUTHORS` answers `CONST_SERVICE_STATUS_UNTRUSTED_COMMENT`. The new test module builds its own signed delivery helper, as `tests/server/routes/test_roadmap_consumer_pull_events.py:178:def _deliver(` does
  - Verification: `$ uv run devops ci test tests/server/routes/test_roadmap_consumer_comment_events.py` passes

## 4. Run the row that a comment wakes, scoped to its issue

Kind: behavior. Reads: `src/devops_cli/roadmap/run.py`, `src/devops_cli/roadmap/implement/implement.py`, `src/devops_cli/roadmap/refine/refine.py`, `tests/roadmap/test_roadmap_run_scoped_update.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`. Changes: `src/devops_cli/roadmap/run.py`, `src/devops_cli/roadmap/implement/implement.py`, `tests/roadmap/test_roadmap_run_scoped_update.py`.
Adds: `scoped_update_of`, `_scoped_clone`, `_refine_one`, `_implement_one`, `comment_asks_retry`

- [ ] 4.1 `test_a_comment_delivery_runs_the_row_that_its_text_wakes` in `tests/roadmap/test_roadmap_run_scoped_update.py`, beside `tests/roadmap/test_roadmap_run_scoped_update.py:117:def _delivery(event: str, action: str, *pulls: int) -> WebhookDelivery:`, for the scenarios `A retry comment clears the stop and submits a Job` and `A trusted reply runs the refine row`: `scoped_update_of` gives the `implement` row for the retry command and the `refine` row for another comment, `_refine_one` passes that one item number to the refine row that `plan_refine` reads, and `_implement_one` runs the implement round on the checkout of its lane
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_run_scoped_update.py` fails on the base
- [ ] 4.2 Add `comment` and `comment_at` to `src/devops_cli/roadmap/run.py:669:class WebhookDelivery:`, add `needs_clone` to `src/devops_cli/roadmap/run.py:1289:class ScopedUpdate:`, and add `scoped_update_of`, `_scoped_clone`, `_refine_one` and `_implement_one` beside `src/devops_cli/roadmap/run.py:682:def _intake_one(`. `run_scoped_update` takes its update from `scoped_update_of` in place of `src/devops_cli/roadmap/run.py:1365:update = SCOPED_UPDATES.get((delivery.event, delivery.action))`, and a runner that needs a clone gets the checkout of its lane from `ensure_checkout` with `lane_clone_dirname`. `_run_refine_adapter` takes `item_number` and passes it to `plan_refine`. Add `comment_asks_retry` beside `src/devops_cli/roadmap/implement/implement.py:261:def retry_asked(comments: Sequence[IssueComment]) -> bool:`, and let `retry_asked` read each comment body through it
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_run_scoped_update.py` passes

## 5. Route a trusted comment to the row of its scoped update

Kind: behavior. Reads: `src/devops_cli/server/routes/webhooks.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/models/webhooks.py`, `tests/server/routes/test_roadmap_consumer_pull_events.py`, `tests/models/test_webhooks.py`, `tests/server/routes/test_k8s_roadmap_service.py`, `tests/server/test_server_service.py`, `tests/telemetry/test_service_counter_series.py`, `tests/server/test_mattermost_slash_command.py`. Changes: `src/devops_cli/server/routes/webhooks.py`, `tests/server/routes/test_roadmap_consumer_comment_events.py`.

- [ ] 5.1 `test_a_trusted_retry_comment_runs_the_implement_row_and_a_trusted_reply_runs_the_refine_row` in `tests/server/routes/test_roadmap_consumer_comment_events.py`: a trusted retry comment runs the scoped update on the lane of the `implement` row and a trusted reply runs it on the lane of the `refine` row, each for the issue number of the delivery, and neither queues a whole round
  - Verification: `$ uv run devops ci test tests/server/routes/test_roadmap_consumer_comment_events.py` fails on the base
- [ ] 5.2 In `deliver` of `roadmap_consumer` in `src/devops_cli/server/routes/webhooks.py`, build the `WebhookDelivery` with the comment body and its time before the row lookup, and take the row from `scoped_update_of` in place of `src/devops_cli/server/routes/webhooks.py:303:scoped = SCOPED_UPDATES.get((event, action))`, keeping the lane choice of `lane_of_row`, the scoped enqueue and the whole-round hint of the existing path
  - Verification: `$ uv run devops ci test tests/server/routes/test_roadmap_consumer_comment_events.py` passes
- [ ] 5.3 Edit the lane-class note of `tests/roadmap/test_roadmap_limit_classes.py` where it names the scoped rows, so the comment row is counted with the lane of its job
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 2: `CONST_ROADMAP_WEBHOOK_EVENTS` includes `"issue_comment"`, and `k8s/README.md` step 8 matches.
- Group 3: `roadmap_consumer` refuses `issue_comment` deliveries from bots, `edited` or `deleted` actions, and authors outside `CONST_ROADMAP_TRUSTED_AUTHORS` before making any GitHub API request.
- Group 5: A trusted `implement: retry` comment on a Service-stopped Blocked issue clears the stop on `status` and submits an eligible runner Job.
- Group 5: Another trusted human comment on an open issue enqueues a scoped `refine` update on the `model` lane for that issue number.
- Group 5: Offline unit tests cover bot refusal, untrusted-author refusal, `implement: retry`, and trusted `refine` reply routing.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
