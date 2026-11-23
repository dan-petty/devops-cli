# Tasks

## 1. Add the pull request, review and check events to the consumer event set

Kind: behavior. Reads: `src/devops_cli/config/constants.py`, `src/devops_cli/server/routes/webhooks.py`, `src/devops_cli/github/onboard/service_rows.py`, `tests/roadmap/test_roadmap_run_due_table.py`, `tests/server/test_server_service.py`, `docs/CLUSTER.md`. Changes: `src/devops_cli/config/constants.py`, `tests/roadmap/test_roadmap_run_due_table.py`, `tests/server/test_server_service.py`, `docs/CLUSTER.md`.

- [ ] 1.1 Write the failing case `test_the_event_set_and_step_8_name_the_same_events` in `tests/server/test_server_service.py` for the scenarios `The event set holds the pull, review and check events` and `The runbook step and the event set name the same events`: each event of `CONST_ROADMAP_WEBHOOK_EVENTS` is named in step 8 of `docs/CLUSTER.md`, and the set holds `issues`, `pull_request`, `pull_request_review` and `check_suite`. Drop the `pull_request` `closed` parametrization of `test_an_event_no_consumer_subscribes_to_gets_no_subscriber_and_starts_no_round`, because the consumer now takes that event, and update the case `test_the_table_runs_the_lanes_in_order_and_names_no_release_job` in `tests/roadmap/test_roadmap_run_due_table.py`, whose last assertion reads `tests/roadmap/test_roadmap_run_due_table.py:131:["issues"],`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_run_due_table.py tests/server/test_server_service.py` fails on the base
- [ ] 1.2 Add `pull_request`, `pull_request_review` and `check_suite` to `CONST_ROADMAP_WEBHOOK_EVENTS` in `src/devops_cli/config/constants.py`, beside the events that the intake keys give, and keep the intake keys as they are. Update the due-table case to expect `["check_suite", "issues", "pull_request", "pull_request_review"]`, update the consumer cases as the test says, and add the new case
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_run_due_table.py tests/server/test_server_service.py` passes
- [ ] 1.3 Edit step 8 of `docs/CLUSTER.md` to name `issues`, `pull_request`, `pull_request_review` and `check_suite`, to say that the roadmap consumer takes them, and to say that `devops repos onboard` requires them of each hook
  - Verification: `$ uv run devops ci docs` passes

## 2. Validate the pull request and check suite payloads

Kind: behavior. Reads: `src/devops_cli/models/webhooks.py`, `src/devops_cli/server/routes/webhooks.py`, `src/devops_cli/roadmap/run.py`, `tests/server/routes/test_k8s_roadmap_service.py`. Changes: `src/devops_cli/models/webhooks.py`, `tests/models/test_webhooks.py` (new).
Adds: `WebhookPullRequest`, `WebhookCheckSuite`, `delivery_numbers`

- [ ] 2.1 Write the failing test `test_a_pull_request_and_a_check_suite_payload_validate` in `tests/models/test_webhooks.py`: a payload with `pull_request` number 42 and a payload with `check_suite.pull_requests` holding 42 both validate, `delivery_numbers` gives (42,) for each, and each has `issue` equal to None
  - Verification: `$ uv run devops ci test tests/models/test_webhooks.py` fails on the base
- [ ] 2.2 Add `WebhookPullRequest` with `number` and `WebhookCheckSuite` with `pull_requests` of `WebhookPullRequest` to `src/devops_cli/models/webhooks.py`, each frozen and with `extra="ignore"`, as the other models of the file are. Add the optional `pull_request` and `check_suite` fields to `GitHubWebhookPayload`, and add the `delivery_numbers` property that gives the issue number, the pull request number, or each number of the check suite, and an empty tuple when the payload names none
  - Verification: `$ uv run devops ci test tests/models/test_webhooks.py` passes

## 3. Read only the delivered pull requests in a watch round

Kind: behavior. Reads: `src/devops_cli/roadmap/watch_row.py`, `src/devops_cli/config/constants.py`, `tests/roadmap/test_roadmap_watch_row.py`. Changes: `src/devops_cli/roadmap/watch_row.py`, `tests/roadmap/test_roadmap_watch_scoped.py` (new).

- [ ] 3.1 Write the failing tests of `tests/roadmap/test_roadmap_watch_scoped.py` for the scenarios `A scoped round reads the delivered pull request`, `A scoped round for an unknown pull request sends no request`, `A round with no numbers reads the listing` and `Open pull requests read via GraphQL`: with open staged drafts 42 and 43, `watch_round` with the pull numbers (42,) reads pull request 42 and sends no request for 43; with (99,) and no record of 99 it sends no request and returns the empty round result; with no numbers it reads the open pull requests with one GraphQL query
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_watch_scoped.py` fails on the base
- [ ] 3.2 Add the keyword `pull_numbers: tuple[int, ...] = ()` to `watch_round`, to `_process_rest_pulls` and to `_collect_rest_candidates` of `src/devops_cli/roadmap/watch_row.py`. With numbers, skip `_read_open_pulls_graphql`, build the REST candidates from the delivered numbers only, a number that the store records as the `stage.pr` of an open item or that the watch ledger holds, and pass the same numbers to `_check_closed_stage_plans` so a delivered closed plan pull request still settles. Any other number sends no request. With no numbers, keep the round of the poll
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_watch_scoped.py` passes

## 4. Run the watch row scoped from a pull, review or check delivery

Kind: behavior. Reads: `src/devops_cli/roadmap/run.py`, `src/devops_cli/roadmap/watch_row.py`, `src/devops_cli/config/constants.py`, `tests/roadmap/test_roadmap_run_scoped_update.py`. Changes: `src/devops_cli/roadmap/run.py`, `tests/roadmap/test_roadmap_run_scoped_update.py`.
Adds: `_SCOPED_WATCH_ACTIONS`, `_SCOPED_WATCH`, `_watch_one`

- [ ] 4.1 Write the failing test `test_a_pull_request_delivery_runs_the_scoped_watch_round` in `tests/roadmap/test_roadmap_run_scoped_update.py` for the scenarios `A pull request delivery runs the scoped watch round`, `A check suite delivery names every pull request of the suite` and `A delivery that matches no staged draft sends no request`: a delivery with the pull numbers (42,) runs `watch_round` for 42 only, and `SCOPED_UPDATES` holds the job `watch` for each pull request, review and check suite action. Update the mapping case `tests/roadmap/test_roadmap_run_scoped_update.py:54:def test_the_issues_actions_run_a_scoped_intake_on_the_lane_of_intake() -> None:`, and update `tests/roadmap/test_roadmap_run_scoped_update.py:96:def test_an_edit_of_an_item_and_an_event_with_no_scoped_update_change_nothing(`, whose `pull_request` `opened` delivery now has a row, so it names `check_suite` `requested` as the event with no scoped update, for the scenario `A closed issue and a check suite that requests checks`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_run_scoped_update.py` fails on the base
- [ ] 4.2 Add the optional `pull_numbers: tuple[int, ...] = ()` to the record at `src/devops_cli/roadmap/run.py:668:class WebhookDelivery:` and make `number` optional with a default of None; `_intake_one` returns an empty `JobOutcome` when the delivery names no issue number. Add `_watch_one`, which runs `watch_round` with `ledger_path` beside `schedule.json` and `pull_numbers=delivery.pull_numbers`, and returns `JobOutcome()`. Add `_SCOPED_WATCH_ACTIONS` with the seven `pull_request` actions, `pull_request_review` `submitted` and `check_suite` `completed`, and `_SCOPED_WATCH` with the job `watch`; build `SCOPED_UPDATES` from the `issues` rows and those rows
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_run_scoped_update.py` passes

## 5. Route a delivery to the scoped watch row from the consumer

Kind: behavior. Reads: `src/devops_cli/server/routes/webhooks.py`, `src/devops_cli/roadmap/run.py`, `tests/server/routes/test_k8s_roadmap_service.py`, `tests/server/test_server_service.py`, `tests/telemetry/test_service_counter_series.py`, `tests/server/test_mattermost_slash_command.py`. Changes: `src/devops_cli/server/routes/webhooks.py`, `tests/server/routes/test_roadmap_consumer_pull_events.py` (new).

- [ ] 5.1 Write the failing test `test_a_signed_pull_request_delivery_runs_the_scoped_update` in `tests/server/routes/test_roadmap_consumer_pull_events.py` for the scenarios `A subscribed pull request delivery runs on the status lane`, `A delivery of the App's own bot starts nothing` and `An unscopeable event keeps a whole-round hint`: a signed `pull_request` `synchronize` delivery with pull request number 42 makes `roadmap_consumer` run the scoped update for 42 and queue no full round on any lane, an unsigned delivery gets 401, a delivery of the App's bot runs no scoped update, and a `check_suite` `requested` delivery keeps a whole-round hint
  - Verification: `$ uv run devops ci test tests/server/routes/test_roadmap_consumer_pull_events.py` fails on the base
- [ ] 5.2 In `roadmap_consumer` of `src/devops_cli/server/routes/webhooks.py`, take the numbers of a delivery from `payload.delivery_numbers`: set `pull_numbers` to those numbers, set `number` to the issue number when the payload holds one, name the first delivered number as the subject of the trigger, scope a delivery that names a number, and keep the refusal of the App's own deliveries and the whole-round hint for an event with no row or with no number. The new test module builds its own signed delivery helper and its own fake of the lanes
  - Verification: `$ uv run devops ci test tests/server/routes/test_roadmap_consumer_pull_events.py` passes
- [ ] 5.3 Update `tests/roadmap/test_roadmap_limit_classes.py`
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1: `CONST_ROADMAP_WEBHOOK_EVENTS` includes `"pull_request"` and `"check_suite"`, and `k8s/README.md` step 8 lists the same events.
- Group 2: `GitHubWebhookPayload` validates `pull_request` and `check_suite` payloads while keeping `issue` optional.
- Group 4: `check_suite` `completed` and `pull_request` draft-change deliveries run a scoped `stage_ready` pass on `status` for the matching `stage.pr` item.
- Group 3: Payloads for pull requests that match no open staged draft make zero `GET pulls/<n>` or `check-runs` requests.
- Group 5: Offline unit tests cover payload parsing, consumer routing, and scoped `stage_ready` execution.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
