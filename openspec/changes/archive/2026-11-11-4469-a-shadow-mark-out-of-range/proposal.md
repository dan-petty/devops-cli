# Proposal: #4469

## Why

`devops roadmap eval jev --from-shadow` stops with `StopIteration` when the mark `intake.jev_shadow` holds a probability above 1 or below 0. `ShadowAnswer` has no bound, so `ShadowObservation.from_mark` accepts the mark. Then `_band` in the report finds no band for the value, and `next` raises. The mark is in the issue body on GitHub, which a person or a tool can change, and the report reads every issue. So one bad mark stops the whole report. Closes #4469.

## What Changes

- `ShadowAnswer.probability` gets the bound `Field(ge=0, le=1)`. `from_mark` then raises `ValidationError` for a mark out of range, and `observed_issues` counts it in `unreadable` and goes on.
- `ShadowIntakeModel.observation` does not change. A Jev answer out of range already counts `jev_error`: the decision model refuses a confidence outside 0 to 1, and a test run with confidence 1.5 and no new catch gives no mark. A new catch of `ValidationError` there would be dead code.
- `_band` does not change. A fallback there would put a bad mark into a band.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-intake-jev`: the shadow mark holds only a probability from 0 to 1.

## Impact

- Code: `src/devops_cli/roadmap/intake/intake_jev_shadow.py`
- Tests: `tests/roadmap/test_roadmap_jev_shadow_report.py`
- No setting, metric or command output changes for a valid mark.

## Feasibility

- Confirmed in the source on origin/main: `ShadowAnswer.probability` is a plain `float`, `BANDS` cover `[0, 1.01)`, `_band` uses `next(...)` with no default, and `observed_issues` catches only `ValidationError`.
- Confirmed by a test run: a mark with `1.5` and a mark with `-0.1` give `([1, 2], 0)` from `observed_issues` before the change (both read as valid), and `unreadable` equal to 1 after it.

## Existing Tool Considered

Pydantic, already a dependency, validates a `NamedTuple` field with `Annotated[float, Field(ge=0, le=1)]` when a model holds it. No new code is necessary. Cost: about 40,000 tokens and 30 minutes to build, nothing to keep.
