# Design

## Decision 1: The open dependencies are an input of the Ready check

`refine_one_item` reads the open dependencies of the validated proposal once, with `_open_dependencies`, and passes the result to `check_ready` and to `next_step_of`. A proposal with a blocker is not Ready. `next_step_of` keeps its order: the open questions go to a person first, then the split, then the blockers, then a suspected block. `next_step_of` no longer takes the store, because it had one reason to read it.

- Rejected: read the store inside `check_ready` and again inside `next_step_of`. In the GitHub store, `item` is one request for each issue, so each dependency would cost two requests.
- Rejected: make `blockers` a default argument of `check_ready`. A default lets a caller forget the input, which is the defect of this issue.
- Rejected: test the dependencies in `next_step_of` before `is_ready`. The Status and the next step would then come from two rules. `is_ready` is the one source for both, and the judge of a bot item reads it too.

## Decision 2: The return path needs no new code

A `blocked` wait ends in `_still_waiting` when no recorded blocker is open, and the item goes through the selection again. The new test of two blockers shows it. With one blocker closed, the item waits on the other with no model call. The round after the last close sets it Ready. The record `refine.blocked_by` holds the numbers that the round found open, and the round after reads their state from the store.

## Decision 3: A run for each item holds the Ready items that already exist

`_refinable` skips a Ready item that has a record of its refine section. Two cases are the exception. The item holds a covering tool that no round asked about, or a bot opened it and the approval does not hold. So no round reads the Ready items that hold an open dependency now. The change fixes the cause, so no new item gets into that state. The existing items get one `devops roadmap refine --item <number> --confirm` run each after the merge. `--item` refines an open Ready item whatever its record says.

- Rejected: a selection rule for a Ready item with an open dependency. The rule reads one issue for each dependency of each Ready item in each round. A read of 2026-11-05 counted 69 Ready items. 18 of them had a Dependencies section, with 25 named dependencies in all. Each round would add about 25 requests for a state that the change stops from arising. The rule would stay in the code after the last of these items is gone. The second option of the issue costs one model call for each existing item, once.
- Rejected: set the Status and the record of these items with a script and no model call. Refine is the one writer of `refine.next_step` and `refine.blocked_by`, and a round writes the comment that tells a reader the reason. A script would be a second writer, and its comment would have no proposal behind it.

## Boundary

#3418 finds a dependency that the proposal does not name. This change honors a dependency that the proposal names. A person can write a dependency under "Dependencies" in the body. The model can leave it out of `dependencies`. The stage job still handles that case, because it reads the whole body.
