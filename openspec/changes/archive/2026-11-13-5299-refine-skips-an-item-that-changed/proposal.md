# Proposal: #5299

## Why

A refine round in the Service reads its items, calls a model for minutes, and then writes each item. When a person, a merged pull request or another job changes an item in that time, the store refuses the write with `RoadmapItemChangedError` before it changes anything (ADR 0002). `RefineWriter.settle` catches that error as a failed write: it logs a WARNING, adds the item to the unwritten items, and logs `result=error class=head_moved`. At the end of the round, `raise_for_failures` raises `RoadmapRefineError`, and the Service logs an ERROR with a full traceback for a normal event. The refine grade counts the item as a failure, but no fix can prevent the race. Refine also has a second check of the same race: when the body outside the refine section changed since the read, `_apply_refined` writes nothing, but the round logs the next step of the item as its result and counts the item as written. Closes #5299.

## What Changes

- The change fits one pull request.
- `RefineWriter.settle` catches `RoadmapItemChangedError` before the other write errors. It logs one INFO line that names the item, and does not add the item to the unwritten items. So the round does not fail for the item, and the next round reads it again.
- A changed item writes no `roadmap job result` line, as an alternatives check whose body a person changed writes none (`docs/roadmap/job-success.md`). So the job grade counts the race neither as a success nor as a failure.
- `_apply_refined` returns `RefineApplied(changed_count=1)` when the body changed since the read. The writer then writes no result line for that item and does not count it as written. Before, it logged the next step of a body that refine did not write.
- `RefineApplied` gets the count `changed_count`.
- A write that fails for another reason stays a failure: the item is unwritten, its line is `error`, and the round raises `RoadmapRefineError`.
- `devops roadmap refine --confirm` (`apply_refine`) does not change: a person who runs it still sees `ROADMAP_ITEM_CHANGED` (#5114).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-refine/writes`: a refine round skips an item that changed since the read, does not count it as a failed write, and writes no result line for it.

## Impact

- Code: `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/lang/en/messages.py`.
- Tests: `tests/roadmap/refine/test_roadmap_refine_round.py`.
- Documents: `docs/roadmap/job-success.md`, `docs/ROADMAP_WORKFLOW.md`.
- Metrics: refine writes fewer result lines, one less for each race. The dashboard and the grade report count the lines, so no query changes. The INFO line `Refine did not write #N ...: the item changed since the read.` shows each race in Loki.
- Release: the Service runs this code, so the fix reaches the Service only with a release and a new image.
- Cost: no new request.

## Feasibility

- Loki, `{namespace="devops", service_name="roadmap-service"}`, last 48 hours: the race happened for #5213 (0.124.0, 2026-11-12T23:58:53Z), #5100 (0.120.0) and for item #34 of another repository (0.126.0, 2026-11-13T05:01:31Z). Each time the round logged `Refine wrote nothing more for #N ...: the write failed (RoadmapItemChangedError).`, then `roadmap job result: job=refine ... result=error success=false class=head_moved infra=false`, then an ERROR `Service job execution failed ... RoadmapRunError ... refine could not write 1 item(s), and went on: #N` with the traceback through `RefineWriter.raise_for_failures`. In the last 7 days, refine logged 3 `error` lines with the class `head_moved` and 1 with the class `provider`.
- Loki, last 7 days: the pre-check `Skipping #23: the body changed between the read and the write.` happened one time. The round logged the next step of that item as its result.
- Source on `main` at 4ef7c6f11: `RefineWriter.settle` (`refine.py:3381`) catches every `DevOpsCLIError` after the credentials and the stop, appends a `RefinedItem` to `_unwritten`, and `raise_for_failures` gives `_unwritten` to `raise_for_failed_items`, which raises. `_apply_refined` (`refine.py:3266`) returns `RefineApplied()` when `_outside_unchanged_since_read` is false, and `settle` then counts the item as written and logs its next step.
- The new tests ran on `main` before the fix (`devops ci fail-to-pass --base origin/main`). The item-changed case and the case of a person who moves the item during the round raised `RoadmapRefineError: refine could not write 1 item(s), and went on: #2`. The case of a body edit during the round logged `result=ready class=none` and `written=3`.
- The issue asks for the line `result=skipped class=head_moved success=true` and says that intake counts `skipped` as an intended result. That premise is not correct: `SUCCESS_RESULTS` of `intake` (`roadmap/job_result.py`) holds only `placed` and `duplicate`, and intake logs `skipped` with `success=false`. The rule of the project for this race is in `docs/roadmap/job-success.md`: an alternatives check whose body a person changed since the read writes no line. The open issue #5166, a child of the job grade issue #5164, plans the same rule for intake. The effect that #5299 gives, 12 of 15 in place of 12 of 16, is the count with no line. So this change writes no line, and does not add `skipped` to the intended results of refine. TypeSafe Jev, asked to pick between the two rules on this evidence, picked "no line" with a probability of 0.99.

## Existing Tool Considered

No open tool runs the refine job of this roadmap. The change reuses the store guard of ADR 0002, the class table of `roadmap/failure.py` and the result line of `roadmap/job_result.py`. It costs about 0.15M tokens to build and test, about 500 tokens to keep, and about 1 hour elapsed.
