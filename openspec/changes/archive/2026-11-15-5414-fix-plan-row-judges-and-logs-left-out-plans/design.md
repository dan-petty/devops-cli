# Design: #5414 fix(roadmap): the fix_plan row judges and logs each plan it leaves out

## Context
ADR 0021 section 8 defines `fix-plan` as one repair of a plan pull request with open findings.
The selection rules specify:
"An open draft plan pull request that holds `plan/needs-fix` and that the record of a Staged item names in `stage.pr`. The item has no runner Job and no claim of an agent or a person. The branch holds only commits of the App."
Currently, `_branch_reason` is evaluated only after selection inside `_attempt`, and mode `plan` stops at the first candidate without logging the rest of the queue.

## Decisions

### 1. Integrate branch checks into `select_fix_plan`
- `select_fix_plan` accepts optional `source: Path | None = None`.
- When evaluating each candidate in `select_fix_plan`, if record and pull status rules pass and `source` is provided, `_branch_reason` checks whether the branch names the item, has moved, or holds commits by another author.
- If a branch check fails, log a warning with the reason, record the candidate as left out, and continue evaluating subsequent candidates in the same round.

### 2. Full candidate evaluation in mode `plan`
- In mode `plan`, `select_fix_plan` evaluates all candidates rather than exiting on the first match.
- The first candidate that qualifies is retained as `selected` (the would-be selection).
- Subsequent candidates that also qualify are marked with `MESSAGES.roadmap.fix_plan_left_round` ("A round takes at most one plan.").
- Candidates that fail any rule are marked with their specific disqualification reason.

### 3. Left-out logging with deduplication
- Implement `log_left_out(repo, left_out, handled=())` following the pattern of `stage_left_out.log_left_out` (#4521).
- Key the logged reason by `(repo, item_number)`.
- A left-out line is emitted only when the reason changes.
- Provide `reset_left_out_log()` for test isolation and register it in `tests/conftest.py`.

### 4. Clear mode `plan` selection logging
- When running in mode `plan` (`confirm=False`), log a mode line:
  "In mode plan, the fix-plan step of {repo} starts no attempt. Mode on would select plan pull request #{pull} of item #{number} at {head}."
- In mode `on` (`confirm=True`), retain `MESSAGES.roadmap.fix_plan_selected`.
