# Tasks

## 1. The row implement removes the labels of a closed issue

Kind: behavior. Reads: `src/devops_cli/roadmap/status_sync.py`, `src/devops_cli/roadmap/implement/implement_submit.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/roadmap/stores/store.py`. Changes: `src/devops_cli/roadmap/status_sync.py`, `src/devops_cli/roadmap/implement/implement_submit.py`, `tests/roadmap/test_roadmap_status_sync.py`, `tests/roadmap/test_roadmap_status_round.py`, `tests/server/test_server_service.py`.
Adds: `clear_closed_labels`, `clear_closed_issues`, `ClosedCleared`

- [ ] 1.1 Write the failing webhook test `test_an_issues_closed_delivery_removes_the_status_label_with_one_request` in `tests/roadmap/test_roadmap_status_round.py`: `run_due_jobs` runs the row `implement` for the trigger `("webhook", "issues", "closed")` of a closed issue that holds `status/ready`, with a last success of the row 1 minute ago, so only the trigger makes the row due. The store gets exactly one label removal, of `status/ready`. Add the action `closed` to `test_the_roadmap_consumer_takes_the_events_its_jobs_read_into_all_three_lanes` in `tests/server/test_server_service.py`, so the router gives that trigger to each lane
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_status_round.py tests/server/test_server_service.py` fails on the base for the new round test
- [ ] 1.2 Write the failing poll test `test_a_closed_issue_that_holds_owner_agent_loses_the_label_in_the_next_round` in `tests/roadmap/test_roadmap_status_round.py`: the row `implement` runs with no trigger for a closed issue that holds `owner/agent`, the label goes, and a second round sends no label removal. In `test_the_label_follows_the_item_from_staging_to_the_close`, remove the hand removal of `status/in-review`, so the round removes it
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_status_round.py` fails on the base
- [ ] 1.3 Write the failing tests of `clear_closed_issues` in `tests/roadmap/test_roadmap_status_sync.py`: a closed issue with `status/in-review`, `owner/agent` and `type/bug` loses the first two only; a closed issue with `status/ready`, `status/in-review` and `priority/p2-medium` gets exactly two removals; a closed issue with only `priority/p2-medium` gets none; an open issue keeps its labels; an issue that a person reopens after the listing keeps `status/ready`; a closed Candidate with `status/new` loses it; a removal that fails does not stop the next issue. Change the docstring of `test_an_issue_that_closed_after_the_cached_read_gets_no_label`, which names the workflow
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_status_sync.py` fails on the base
- [ ] 1.4 Add `clear_closed_labels`, `clear_closed_issues` and `ClosedCleared` to `src/devops_cli/roadmap/status_sync.py`, and describe them in the module docstring. Call `clear_closed_issues` in `run_implement_round` after the first `sync_statuses`, and add its failures to `status_failed` of each result
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_status_sync.py tests/roadmap/test_roadmap_status_round.py tests/server/test_server_service.py` passes

## 2. Remove the workflow and the onboard row

Kind: behavior. Reads: `src/devops_cli/roadmap/onboard.py`, `src/devops_cli/roadmap/request_plan.py`, `tests/roadmap/test_roadmap_onboard.py`. Changes: `.github/workflows/clear-status.yml`, `src/devops_cli/roadmap/onboard.py`, `src/devops_cli/roadmap/request_plan.py`, `tests/roadmap/test_roadmap_onboard.py`.

- [ ] 2.1 Change `tests/roadmap/test_roadmap_onboard.py` to the six rows: the seed holds no `clear-status.yml`, every row is `present` and the output holds no `clear-status`, row 5 is `The repository is in service.repos`, the webhook row is row 6, and the dry run lists no read of `.github/workflows/clear-status.yml`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_onboard.py` fails on the base
- [ ] 2.2 Delete `.github/workflows/clear-status.yml`. In `src/devops_cli/roadmap/onboard.py`, delete `_CLEAR_STATUS_PATH`, the row-5 constant and `_check_row_5`, number the `service.repos` row 5 and the webhook row 6, and change the docstrings from seven to six. In `onboard_requests` of `src/devops_cli/roadmap/request_plan.py`, delete the read of the workflow file and its name in the docstring
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_onboard.py` passes

## 3. Name the Service in the docstrings

Kind: other. Reads: `src/devops_cli/roadmap/inbox.py`, `src/devops_cli/roadmap/pull_status.py`. Changes: `src/devops_cli/roadmap/inbox.py`, `src/devops_cli/roadmap/pull_status.py`.

- [ ] 3.1 Change the module docstrings of `inbox.py` and `pull_status.py` so that they name the row `implement` of the Service as the remover of the labels of a closed issue
  - Verification: `$ ! git grep -n clear-status -- src/ tests/roadmap/ tests/server/`

## 4. Name the Service in the documents

Kind: other. Reads: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/onboard.md`, `docs/CLUSTER.md`, `docs/adr/0016-labels-hold-the-roadmap-items-fields.md`, `docs/adr/README.md`. Changes: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/onboard.md`, `docs/CLUSTER.md`, `docs/adr/0016-labels-hold-the-roadmap-items-fields.md`.

- [ ] 4.1 In `docs/ROADMAP_WORKFLOW.md`, name the row `implement` of the Service as the actor of the close in the Status and the Owner tables, in the sentence after the label table and in gate G2. In `docs/roadmap/onboard.md`, write six prerequisites and remove the workflow row. In row 16 of `docs/CLUSTER.md`, state that a round removes the `status/*` and `owner/*` labels of each closed issue, and that an `issues.closed` delivery makes the row due. Add the line `2026-11-22: Amended by the owner decision in #4627, section One label family for each field: the Service removes the labels of a closed issue (#4660).` to the Status History of ADR 0016
  - Verification: `$ uv run devops ci docs` passes, and `$ uv run devops ci test tests/invariants/test_adr_records.py` passes

## Workflow follow-up

- Pending a person: after the merge and the deploy, close a test issue that holds a `status/*` label in one other repository of `service.repos`, and check that the label goes within 5 minutes.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
