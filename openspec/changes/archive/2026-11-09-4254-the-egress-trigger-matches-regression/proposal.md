# Proposal: #4254

## Why

The stage job matched each security trigger word as a plain substring. The word `regression` holds `egress`, so a test-only plan that said "regression" needed a `## Security` section. The live run on item #4062 refused a plan for this reason and spent its one return on it (#4254).

## What Changes

- `_matched_security_trigger` matches each word of `SECURITY_TRIGGER_WORDS` as a word, not inside a longer word. A letter next to the match ends it. A plural ending (`s`, `es`) is allowed. A phrase such as `admission policy` matches as a phrase.
- The trigger paths keep their plain substring match.
- The requirement "A security trigger needs a security section" gets a scenario for a trigger word inside a longer word. The change has an observable effect on the stage job, so it carries a spec delta.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: a security trigger word matches only as a word.

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_change.py`
- Tests: `tests/roadmap/stage/test_roadmap_stage_security.py`
- The change fits one pull request.

## Feasibility

- The live run of 2026-11-09 on item #4062 refused a test-only plan with "The plan matches the security trigger `egress`". The word `regression` holds the letters `egress`: `"egress" in "regression"` is true in Python.
- The new test `test_a_trigger_word_inside_a_longer_word_needs_no_security_text` fails on origin/main with that exact problem, and passes with the change.
- The golden set of the stage eval replays through the gates: `uv run devops roadmap eval stage --replay`.

## Existing Tool Considered

The standard library `re` with a look-around on letters and `re.escape`. No new library and no new helper: one compiled pattern for each trigger word replaces the substring test. The code deleted is the `casefold` substring loop.
