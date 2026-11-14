# Design

## Context

`plan_check` reads the check summary once and `_check_problems` reports every state that is not a pass. `read_check_runs` returns `in_progress` while the required check runs. The job starts at once because `always()` cancels the wait of `needs`.

## Goals

- Never fail on a title check that is merely slow.
- Still report a failed title check.
- Keep the job after a failed `semantic-title`.

## Decisions

- **`!cancelled()`.** It runs the job after a failed needed job, like `always()`, and skips the job in a cancelled run.
- **A bounded poll of 120 seconds at 5-second intervals.** The job has a 10-minute timeout, and a cold runner can need longer than 30 seconds.
- **A note at the limit, and no problem.** The required `Semantic PR title` check gates the merge on its own. A failure at the limit would bring back the false failure.
- **`PlanCheckResult.notes`.** The command prints the note, and `ok` reads only the problems.

## Risks

- A title check that is still pending after 120 seconds gives a pass with a note. The required check still blocks the merge until it passes.

## Tests

- A pending check that becomes a pass gives no problem and no note.
- A pending check at the limit gives one note and no problem.
- A failed check gives a problem.
- The workflow condition holds `!cancelled()`, no `always()`, and `needs: semantic-title`.
