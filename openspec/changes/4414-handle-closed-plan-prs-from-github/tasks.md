# Tasks

## 1. Declare the closed pull request key on the two rows

Kind: behavior. Reads: `src/devops_cli/config/constants.py`, `src/devops_cli/roadmap/run.py`, `tests/roadmap/test_roadmap_run_webhook_keys.py`, `tests/support/roadmap_run.py`. Changes: `src/devops_cli/config/constants.py`, `tests/roadmap/test_roadmap_run_webhook_keys.py`.

- [x] 1.1 Add a test named `test_a_closed_plan_pull_request_makes_the_stage_and_implement_rows_due` in `tests/roadmap/test_roadmap_run_webhook_keys.py`, which asserts with every row fresh by its interval that the batch `{("webhook", "pull_request", "closed"): 1}` runs the `stage` and `implement` rows and no other row
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_run_webhook_keys.py` fails on the base
- [x] 1.2 Add `("webhook", "pull_request", "closed")` to `CONST_ROADMAP_STAGE_BATCH_KEYS` in `src/devops_cli/config/constants.py`, with a comment that a merged plan hands its change folder to the implement row and a rejected plan frees a `planned_limit` slot. Write the test in `tests/roadmap/test_roadmap_run_webhook_keys.py` beside `test_an_issues_key_makes_due_only_the_rows_that_declare_it`, with `stamp_successes`, `build_stub_table` and `poll_round` of `tests/support/roadmap_run.py`, and assert that the set of rows that ran is exactly `stage` and `implement`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_run_webhook_keys.py` passes

## 2. Wake the two lanes on a closed plan pull request

Kind: behavior. Reads: `src/devops_cli/roadmap/run.py`, `src/devops_cli/server/routes/webhooks.py`, `tests/roadmap/test_roadmap_run_webhook_keys.py`, `tests/support/roadmap_run.py`. Changes: `src/devops_cli/roadmap/run.py`, `tests/roadmap/test_roadmap_run_webhook_keys.py`.

- [x] 2.1 Add a test named `test_a_closed_plan_pull_request_wakes_the_lanes_of_its_rows` in `tests/roadmap/test_roadmap_run_webhook_keys.py`, which asserts that a `pull_request` `closed` delivery wakes the other lanes and that an `issues` `closed` delivery does not
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_run_webhook_keys.py` fails on the base
- [x] 2.2 Change `scoped_update_wakes_lanes` in `src/devops_cli/roadmap/run.py` so it also returns True when the event of the delivery is `pull_request` and its action is `closed`, beside the `edited` action and the critical placement. Write the test in `tests/roadmap/test_roadmap_run_webhook_keys.py` beside `test_a_scoped_update_wakes_the_other_lanes_for_an_edit_or_a_critical_placement`, with `webhook_delivery("closed", 42, event="pull_request")` of `tests/support/roadmap_run.py` and a case of `webhook_delivery("closed", 42)`, which keeps the `issues` event
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_run_webhook_keys.py` passes

## 3. Prove the two closed plan outcomes with the rows

Kind: other. Reads: `tests/roadmap/implement/test_roadmap_implement_submit.py`, `tests/support/roadmap_run.py`, `tests/support/fakes/roadmap_store.py`. Changes: `tests/roadmap/test_roadmap_closed_plan_webhook.py` (new).

- [x] 3.1 Write `tests/roadmap/test_roadmap_closed_plan_webhook.py` with the clone fixture, the fake GitHub edge and the fake Kubernetes edge of `tests/roadmap/implement/test_roadmap_implement_submit.py`, and the batch and store helpers of `tests/support/roadmap_run.py`. Add `test_a_merged_plan_sets_planned_and_submits_one_job`, which runs the `implement` row with the closed batch and asserts the label `status/planned` and one `devops-cli-runner` Job; `test_an_unmerged_plan_records_the_rejection`, which runs the `stage` row and asserts the rejection record, the reason comment, the deleted session-only branch and the label `status/new`; and `test_a_closed_pull_request_of_no_item_changes_nothing`, which asserts no item change, no Job and no model request
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_closed_plan_webhook.py` passes

## 4. Document the closed plan pull request flow

Kind: other. Reads: `docs/CLUSTER.md`, `k8s/README.md`, `tests/roadmap/test_roadmap_limit_classes.py`. Changes: `docs/CLUSTER.md`, `k8s/README.md`.

- [x] 4.1 Add the key to the batch keys of `stage` and `implement` in step 8 of `docs/CLUSTER.md`, with the two outcomes: a merged plan sets `status/planned` and submits the runner Job, and an unmerged plan records the rejection and returns the item to New. Add the same flow to the `all` stack row of `k8s/README.md`, with no secret, no host name and no address
  - Verification: `$ uv run devops ci docs` passes
- [x] 4.2 Verify in `tests/roadmap/test_roadmap_limit_classes.py` that `CONST_ROADMAP_STAGE_BATCH_KEYS` requires no entry in the numeric limits table, leaving the limit registry unchanged
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 3: A `pull_request` `closed` webhook with `merged=true` syncs `status/planned` and submits the next eligible `implement` Job when none runs.
- Group 3: A `pull_request` `closed` webhook with `merged=false` for `stage.pr` records `stage.rejected`, comments the reason, deletes a session branch, and sets `status/new`.
- Group 3: A closed pull request unrelated to roadmap items leaves all items unchanged and calls no LLM.
- Group 4: Offline unit tests verify both `merged=true` and `merged=false` webhook deliveries, and `k8s/README.md` documents the event flow.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
