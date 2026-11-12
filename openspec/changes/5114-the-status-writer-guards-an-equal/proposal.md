# Proposal: #5114

## Why

`write_status` in `src/devops_cli/roadmap/status_sync.py` compares the derived Status with the label of the Item that its caller read. When they are equal, it writes the marks and the body of its caller with `set_marks`, which has no ADR 0002 guard. Before #5109, refine and the stage returns wrote with `set_field`, which reads the issue and raises `RoadmapItemChangedError` when someone changed the Status since the read. Refine reads its items, calls a model for minutes, and then writes. When the sweep, `devops pr create`, `devops roadmap return`, a stage return or a person changes the label in that time, refine now writes its marks and its body, posts its Ready comment and counts the item as ready, and the label stays as the other writer set it. The lost write is silent, which is the opposite of the goal of #5018. Closes #5114.

## What Changes

- The change fits one pull request.
- `set_marks` of the store gets the keyword `unchanged`. When it names a field, the store compares the value that the issue holds at its read before the write with the value that the store read (the value of the Item, or the last value that the store wrote), as `set_field` does. A difference raises `RoadmapItemChangedError` before any write.
- `write_status` gives `unchanged=ItemField.STATUS` when the label is equal. So a write of the marks and the body on an equal label fails as a label write does when someone changed the Status since its caller read the item. The equal path still writes no label and records no Status, as the design of #5018 decided, and it sends no read after the write.
- The GitHub store and the fake store implement the guard. Three test doubles that override `set_marks` forward the new keyword.
- A consumer observes the change: a write of an equal Status that a parallel writer made old now fails with `ROADMAP_ITEM_CHANGED`. So the change carries a delta of `roadmap-item-labels`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-item-labels`: the one Status writer refuses the marks and the body of an equal label when someone changed the Status since its caller read the item.

## Impact

- Code: `src/devops_cli/roadmap/status_sync.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stores/github_store.py`.
- Tests: `tests/roadmap/test_roadmap_status_sync.py`, `tests/roadmap/stores/test_roadmap_store_contract.py`, `tests/roadmap/refine/test_roadmap_refine_one_write.py`, the fake store (`tests/support/fakes/roadmap_store.py`) and three test doubles in `tests/roadmap/refine/` and `tests/roadmap/stage/`.
- Documents: `docs/ROADMAP_WORKFLOW.md`.
- Cost: no new request. `set_marks` of the GitHub store already reads the issue before its `PATCH`; the guard compares that read.
- Each caller already handles `RoadmapItemChangedError`, because `set_field` raised it before #5109: the refine round counts the item as unwritten and goes on (`_RefineRound.settle`), and the failure class is `HEAD_MOVED`.
- The Service runs this code, so the pull request waits for the owner's "safe and vetted" call before it merges.

## Feasibility

- Source on `main` at 77bdb1f90: `write_status` calls `store.set_marks(item, marks or {}, body=body)` when `item.status` equals the derived Status (`status_sync.py:143-144`), and `set_marks` of `github_store.py` calls no `require_unchanged`. `_apply_refined` calls `write_status(store, r.item, StatusFacts(), marks=marks, body=r.new_body)` with the Item from the start of the round (`refine.py:3280`).
- The new test `test_the_status_writer_refuses_the_marks_when_another_writer_changed_an_equal_label`, run on `main` with `InMemoryRoadmapStore`, failed with `DID NOT RAISE RoadmapItemChangedError`: the writer wrote the marks and the body, and the label stayed New.
- `require_unchanged(name, field, read, now, value, operation)` returns when `read == now` or `value == now`. With `value=read`, it returns only when the issue still holds the value that the store read, so the guard needs no new function.

## Existing Tool Considered

No open tool writes the labels of this roadmap. The change reuses `require_unchanged` of the store and the read that `set_marks` already makes. It costs about 0.2M tokens to build and test, about 1,000 tokens to keep, and about 2 hours elapsed.
