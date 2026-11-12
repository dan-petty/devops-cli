# Proposal: #5018

## Why

`derive_status` in `src/devops_cli/roadmap/status_sync.py` holds the one rule of the Status, but each job wrote the Status label in its own way: 14 calls of `set_field(..., ItemField.STATUS, ...)` in 9 modules, and one more through the generic field loop of intake. Only the sweep read the issue again, and only before its write. No writer read the label back after the write, so a write that a parallel writer lost stayed lost (#4555). Closes #5018.

## What Changes

- The change fits one pull request.
- `status_sync.py` gets the one Status writer, `write_status(store, item, facts, *, dry_run, marks, body)`. It derives the Status from the facts that its caller gives, writes the label only when it differs from the label of the item (with `marks` and `body` in the same write), and reads the issue again after the write. A label that differs from the written Status raises the new `RoadmapStatusLostError` (`ROADMAP_STATUS_LOST`). When the label is equal, it writes only `marks` and `body`, with no read. A dry run sends no request and returns the would-be write as a `StatusWrite`.
- `StatusFacts` gets three facts, so that the one rule gives every Status that a job writes: `needs_refine` (New: intake filed the item, or a job returned it), `pull_ready` (In Review) and `pull_open` (In Progress). The order of `derive_status` is New, In Review, In Progress, Blocked, Planned, Ready.
- Every writer calls `write_status`, with no shim: the runner Job (In Progress, In Review, Blocked), the Job report (Blocked), the clear rules of a stop, the stage returns (a rejected plan, open blockers, a false premise, the plan-defect limit), refine (Ready and New), repair (Ready), intake (New), `devops roadmap return` (New), and `devops pr create` and `devops pr ready` (`pull_status.py`). `sync_status` of the sweep calls it too, so the rows `stage`, `stage_ready` and `implement` get the read-back.
- The store gets `issue(number)`, one read of an issue, Item or not. The writer reads the label back through it, because intake writes New before the Priority that makes the issue an Item, and `item(number)` gives None for such an issue. `item(number)` of the GitHub store now uses it.
- The dry-run request plans of these jobs list the read of the issue after each Status write (`StoreRequests.write_status`, and the step `status_read_back` of intake).
- A structural test fails when a module of `src/` other than `status_sync.py` and the stores calls `set_field` with `ItemField.STATUS`, or adds or removes a `status/` label.
- This changes what a consumer observes (a lost write now fails with an error code, and each dry-run plan lists one more read), so the change carries a delta of `roadmap-item-labels`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-item-labels`: one function derives every Status that a job writes, and one writer writes it and reads it back.

## Impact

- Code: `src/devops_cli/roadmap/status_sync.py`, `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/implement/implement_submit.py`, `src/devops_cli/roadmap/stop_clear.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/repair.py`, `src/devops_cli/roadmap/intake/intake.py`, `src/devops_cli/roadmap/intake/intake_requests.py`, `src/devops_cli/roadmap/return_item.py`, `src/devops_cli/roadmap/pull_status.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stores/github_store.py`, `src/devops_cli/exceptions/roadmap.py`, `src/devops_cli/lang/en/messages.py`.
- Documents: `docs/ROADMAP_WORKFLOW.md`, `docs/ERRORS.md` (generated).
- Tests: `tests/roadmap/test_roadmap_status_sync.py`, `tests/invariants/test_architectural_invariants.py`, `tests/roadmap/stores/test_roadmap_store_contract.py` and the fake store (`tests/support/fakes/roadmap_store.py`), and the tests of the dry-run plans and the request counts that count the new read.
- Cost: each Status write that changes the label costs one more GitHub read. A sweep round writes a few labels, so the cost is a few reads for each round.
- The Service runs this code, so the pull request waits for the owner's "safe and vetted" call before it merges.

## Feasibility

- Source on `main` at 21b116eac: the structural test of this change, run before the change, names 14 direct Status writes: `implement_run.py` (3), `implement_submit.py` (1), `stop_clear.py` (1), `pull_status.py` (1), `refine.py` (2), `repair.py` (1), `return_item.py` (1) and `stage.py` (4). Intake writes the Status in its generic field loop (`_apply_placement`), which the test cannot see, so the change handles it by hand.
- The issue names `claim.py:163` and `claim.py:176`. On `main`, these lines call `store.set_field(item, ItemField.OWNER, ...)`: they write the Owner, not the Status, so the change leaves them as they are. The issue also names `stage_ready.py:134` and `run.py` (`_run_stage_adapter`): they call `sync_status` and `sync_statuses` of `status_sync.py`, which now call `write_status`.
- #4555 is open, so the store has no record read-back yet. The writer reads the label back with one read of the issue (`issue_args` in `github_store.py`, a plain `GET` with no cache). The record read-back of #4555 can go into the writer when #4555 merges.
- A first run of `tests/roadmap` with a read-back through `store.item` failed 123 tests, most of them intake placements, with `RoadmapStatusLostError: ... shows no Status label`: intake writes New before the Priority, and `item` gives None for an issue with no Priority. So the read-back reads the issue (`store.issue`).
- #4660 and #4685 are open and add no writer yet. They call `write_status` when they are built.
- `status_sync.py` imported `stage.stage` and `planned` at the top. With `stage.py`, `refine.py` and `intake.py` now importing `status_sync.py`, pytest stopped at the import cycle `plan_read` → `stage_change` → `refine` → `intake` → `status_sync` → `planned` → `plan_read`. The change imports `PlannedChanges` and `StageFailure` for type checks only, and `write_each` inside `sync_statuses`, as `refine.py` imports `StageClient`.

## Existing Tool Considered

No open tool writes the labels of this roadmap. The change reuses `derive_status`, the family replace of the store (`set_field`) and its read of an item, and deletes the 14 direct writes and the duplicate New guard of `_reject_plan`. It costs about 0.4M tokens to build and test, about 2,000 tokens to keep, and about 4 hours elapsed.
