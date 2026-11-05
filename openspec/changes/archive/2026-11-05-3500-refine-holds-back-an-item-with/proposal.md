# Proposal

## Why

Issue #3500: refine sets an item to Ready while the proposal of the item names an open issue as a dependency. The stage job then leaves the item out, because it reads the same dependency from the body. The item gets no signal, the Ready count is too high, and a reader of the labels sees work that no job can take.

The cause is in `src/devops_cli/roadmap/refine.py`. `check_ready` reads no dependency. `next_step_of` returns `NextStep.READY` before it reads the dependencies, so a proposal with a dependency and no suspected block is Ready. A test helper had to set `suspected_block` to reach `NextStep.BLOCKED`, which the model does not always do.

## What Changes

- A validated proposal can have no open question and fit one pull request, and still name an open issue as a dependency. Refine then gives it the next step `blocked`. The open issues are the details of that step. They go in `refine.blocked_by` and in the comment. Refine does not set the item to Ready. A Ready item goes back to New.
- A dependency that is closed holds nothing back.
- `refine_one_item` reads the open dependencies once. `check_ready` takes them as `blockers` and refuses a proposal that has one. `next_step_of` takes them too, and no longer reads the store.
- The return path is unchanged: `_still_waiting` ends a `blocked` wait when every recorded blocker is closed, and the next round refines the item again.
- The Ready items that already hold an open dependency get one `devops roadmap refine --item <number> --confirm` run after the merge. The change adds no selection rule for them (see the design).
- The change alters the behavior of a devops command, so it carries a spec delta: two ADDED requirements in `roadmap-refine`.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `roadmap-refine`: an open dependency that the proposal names blocks the item.

## Impact

- `src/devops_cli/roadmap/refine.py`.
- `tests/roadmap/test_roadmap_refine.py`.
- `docs/roadmap/refine.md`.

## Feasibility

- The premise holds against the real code. Two of the three new tests fail on `origin/main`. They show the claim of the issue. A proposal with one open dependency and no suspected block gives `is_ready` true and the next step `ready`. Its `blocked_by` is empty and its Status is Ready. The third test, a closed dependency, passes on `origin/main`. It is the guard that a closed dependency stays free.
- The code confirms the other claims. `check_ready` has no dependency input. `next_step_of` returns on `is_ready` before it reads `proposal.dependencies`. `_Judge._dependency` in `stage.py` reads `body_dependencies(item.body)` and leaves out an item with an open dependency. `_still_waiting` with the step `blocked` returns None when no recorded blocker is open, so the item is refined again.
- A read of the repository on 2026-11-05 used no model and made no write. Of 69 Ready issues, 18 hold a Dependencies section. Ten of those name an open issue. The issue counted 9 on 2026-11-04. The set changes each day, so the change records no list.
- The read now runs once for each named dependency of every validated proposal. That includes a proposal with an open question or a split. The old read in `next_step_of` ran only after those returns. A round refines at most `--limit` items (default 3), so the extra reads have a bound.
- The one run per item after the merge is the second option of the acceptance criteria. It needs a model call for each item. The model may leave a dependency out of its new proposal. Then the item stays Ready, and the stage job leaves it out as before.

## Existing Tool Considered

Existing project code covers the need: `_is_open`, `recorded_blockers`, `_still_waiting` and `next_step_of` in `refine.py`. The change adds no library and one small reader, `_open_dependencies`, which is the line that `next_step_of` held before. The change deletes that line from `next_step_of` and the `store` parameter that only it used.
