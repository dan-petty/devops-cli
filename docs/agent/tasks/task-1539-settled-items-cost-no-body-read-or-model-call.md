# Task: A settled item costs no body read or model call until its text changes, with refine judging it from the listing it already read (#1539)

**Issue**: [#1539](https://github.com/dan-petty/devops-cli/issues/1539)
**Scope**: type/bug, scope/roadmap, scope/ai
**Feasibility**: Checked on release/v0.2.39 (f4177632). `IssueRecord` already carries the issue's `body` from the REST listing (`src/devops_cli/roadmap/store.py`) and `join_items` builds every Item of both stores from `IssueRecord.model_dump(...)`, so `Item.body` needs no request beyond the listings, which the recorded-`gh` GitHub store test shows. `_consider` made one `read_issue_body` call for each item it checked, and on the GitHub store that is an uncached REST read. The size guard in `refine_one_item` returned empty hashes and `apply_refine` skips every item with a skip reason, and `plan_refine` caught `AIClientError` and recorded nothing, so neither kind of item was ever recorded; the callers (`devops roadmap refine --confirm` and the refine job of `devops roadmap run`) apply a plan only when `has_writes` is true, which only counted refined items. `chat_structured` turns a `ReplyRejectedError` into a `StructuredOutputValidationError` after its repair loop (`src/devops_cli/ai/client/structured.py`), so end to end only the second class reaches refine; both are classified as the item's own failure, and `ReplyRejectedError` is covered by a fake client that raises it.

## Description

Selection now judges every item by what it already holds, and the two kinds of item that were spent again in every round are recorded.

- **`Item.body`** (`src/devops_cli/roadmap/store.py`) is the issue's body as the listing the Item came from read it. Both stores get it from the listing they already read (`items()`, `items(release=)`, `backlog()` and `item()`), so no request is sent per item. `RefineRecordKey.FAILED_BODY_HASH` (`refine.failed_body_hash`) is the one new job record key.
- **Selection reads no body.** `_consider` (`src/devops_cli/roadmap/refine.py`) hashes `it.body` instead of calling `store.read_issue_body`, so an item whose recorded hashes match its text costs no body read and no model call (since #1758 it waits on its recorded next step), and a Ready item with a recorded section is not considered at all. `refine_one_item`'s own read and `apply_refine`'s re-read before every write stay, so a body a person edited after the listing is still caught before any model call or write. The `--item` path keeps its one read.
- **An item too big to refine is recorded.** When the refined body would pass `CONST_ROADMAP_REFINE_MAX_BODY_CHARS`, `refine_one_item` returns the hashes of the body it read and marks the result `record_only`. `plan_refine` counts such an item in `has_writes`, and `apply_refine` re-reads the body and, when it is unchanged, records the body and section hashes. It writes no body, no Status and no `refine.needs_split`. The next round reads the item as unchanged.
- **A failure the item caused is recorded.** `RefineFailure.of` marks a `StructuredOutputValidationError` or a `ReplyRejectedError` as `item_caused`. `plan_refine` counts it in `has_writes`. `apply_refine` re-reads the body against the hash of the listed body, and then records the failure: the first failure on a body sets `refine.failed_body_hash`, and a second failure on the same body records the body and section hashes and clears the key, which settles the item. A success clears the key. A plain `AIClientError` (a timeout, a 5xx, a dropped stream) records nothing, so the item stays due.
- `plan_refine` stays free of writes; the records are written only by `apply_refine`, behind `--confirm` and in the job.

## Acceptance Criteria

- [x] A refine round makes no `read_issue_body` call and no model call when every New item's recorded hashes match its body and every Ready item has a recorded section (`tests/test_roadmap_refine.py::test_a_round_after_refine_left_items_new_leaves_them_waiting_reading_no_body_or_model`).
- [x] Editing one New item's body outside the section selects only that item, with one body read and one model call, and writes nothing in the planning round; the needs-split items left unchanged wait on their split (`test_editing_one_settled_items_body_selects_only_it_with_one_body_read_and_one_model_call`).
- [x] An item whose refined body would exceed 65,536 characters is selected once, then waits on a body edit until its body changes, and its body is never written (`test_an_item_whose_refined_body_is_too_big_is_selected_once_and_its_body_never_written`).
- [x] An item whose model reply fails the schema twice in a row on the same body waits on a body edit until its body changes (`test_two_replies_that_never_validate_on_the_same_body_settle_the_item`). One failure followed by a success refines it and leaves no `refine.failed_body_hash` (`test_a_failure_followed_by_a_success_refines_the_item_and_clears_the_failure`).
- [x] A `StructuredOutputValidationError` and a `ReplyRejectedError` are recorded, and a plain `AIClientError` is not (`test_only_a_failure_the_items_own_text_caused_is_recorded`). An item whose model call fails twice with a gateway timeout records nothing, and the next round selects it again (`test_a_gateway_failure_records_nothing_and_the_next_round_selects_the_item_again`).
- [x] A round whose only selected item is too big, or fails on its own text, still writes its record through the plan-then-apply path of `devops roadmap refine --confirm` (`test_a_round_whose_only_item_is_too_big_or_fails_still_records_it_through_the_cli`) and of the refine job of `devops roadmap run` (`test_the_runs_refine_job_records_an_item_too_big_to_refine`).
- [x] `plan_refine` writes no body and no record in these cases (`test_planning_a_round_writes_no_body_and_no_record_for_an_item_too_big_or_failing`), and a body that changed between the plan and the apply is left unrecorded with the existing warning (`test_a_body_edited_between_the_plan_and_the_apply_is_recorded_as_neither_too_big_nor_failed`).
- [x] Both stores return `Item.body` from the listing: the in-memory store from `items()`, `items(release=)`, `backlog()` and `item()` (`tests/test_roadmap_store_contract.py::test_an_item_carries_the_body_of_the_issue_listing_it_was_read_from`), and the GitHub store from `items(release=)` and `backlog()` with only the listing requests sent, none per issue (`tests/test_roadmap_github_store.py::test_items_carry_the_body_of_the_listing_they_were_read_from_with_no_request_per_issue`).
- [x] `changelog.d/1539.md` lists the settled items under `### Changed` and #1526's part under `### Fixed`.
- `uv run devops ci` is the pull request's gate.
- Pending a person: with this change checked out, run `devops roadmap refine --repo dan-petty/devops-cli --confirm`, then `devops roadmap refine --repo dan-petty/devops-cli`, and edit no issue in between. The second run selects none of the items the first round refined or found unchanged: it lists each under the heading of the next step it waits on and sends no model request for it.
- Pending a person: delete #698's 6 stacked blocks, each running from a refine start marker (`<!-- devops-roadmap-refine:start -->`) to a literal `[end-marker]` line; the body is 57,664 characters, near the 65,536 cap. Do the same in the managed repositories' items that hold such blocks. This does not gate the change.

## Decisions and deviations

- **Only a failure the item causes settles it** (owner decision D10, 2026-10-17). A `StructuredOutputValidationError` or a `ReplyRejectedError` means the model answered about this item and no answer validated; a gateway outage must never settle every item it touched until each body changes, so a plain `AIClientError` records nothing.
- **The classification is one `isinstance` in `RefineFailure.of`**, not a second `except` clause in `plan_refine`, so `plan_refine` keeps its shape and `AICredentialsError` still stops the run at the first item.
- **The records are written by `apply_refine` alone**, each after a re-read of the issue. The failure record uses the hashes of the body listed at selection, because the failed call returns no other text. The oversize record uses the hashes of the body `refine_one_item` read, which is the text the proposal was about. `apply_refine` compares the re-read body outside the section with the stored hash before it writes either record, so a body that changed since the hashed text records nothing, and `plan_refine` stays write-free.
- **`RefinedItem.record_only` is an explicit marker** rather than a test for an empty hash, because a person-edit skip also has a skip reason and must record nothing.
- **A success clears `refine.failed_body_hash` in the marks it already writes**, so the key never outlives the failure it records.

## Known limits

- After a transport failure the item stays due: the job fails, and the Service reruns it at every poll. This is moot while `deployment/roadmap-service` is held at 0 replicas, and under #1535 each enhancement step is its own retry boundary.
- The Valkey half of the original design, a password-protected cache for intake's embeddings, moved to #1655.
- GitHub reads that spend no model work, such as the full board read at each poll, belong to #1533 and #1535.

## Deliverables

- [x] `src/devops_cli/roadmap/store.py`: `Item.body` and `RefineRecordKey.FAILED_BODY_HASH`.
- [x] `src/devops_cli/roadmap/refine.py`: selection from the listed body, the oversize record, the failure record, `has_writes`, the module docstring.
- [x] `tests/test_roadmap_refine.py`, `tests/test_roadmap_store_contract.py`, `tests/test_roadmap_github_store.py`.
- [x] `docs/agent/tasks/task-744-item-refinement-to-ready.md` and `docs/agent/tasks/task-1515-refine-hourly-nearest-release-first.md`: the lines this change makes stale.
- [x] `changelog.d/1539.md`.
