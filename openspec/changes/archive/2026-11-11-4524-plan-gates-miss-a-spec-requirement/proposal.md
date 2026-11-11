# Proposal

## Why

A stage plan can hold a spec delta requirement whose text has more than 500 characters. Every stage gate and `devops roadmap plan-check` accept it. The implement run then stops at its last step: `openspec archive` merges the delta into the spec, and `openspec validate --all --strict` refuses the merged spec with "Requirement text is very long (>500 characters)". Closes #4524.

Item #3462 shows it. Its plan (PR #4435) modified the requirement `A test-only other group names its test function` of `roadmap-stage` with a text of 543 characters. The implement run (PR #4465) did both groups and stopped at the archive.

## What Changes

- New constant `REQUIREMENT_MAX_CHARS = 500` in `src/devops_cli/roadmap/stage/stage_change.py`. Its comment names the OpenSpec rule `MAX_REQUIREMENT_TEXT_LENGTH`.
- New function `_length_problems` in `stage_change.py`. `_delta_problems` calls it for each capability of the spec delta, so `check_proposal` refuses each ADDED and MODIFIED requirement whose text is longer than the limit. The problem goes to the gate `spec-delta`. `devops roadmap plan-check` runs `check_proposal`, so it reports the same problem with the rule `stage`.
- The count is in UTF-16 code units, as OpenSpec counts a JavaScript string.
- New message `stage_problem_requirement_long`. It names the requirement, its length and the limit.
- New golden case `3462-a-modified-requirement-over-the-limit` with the plan of PR #4435. The replay lists its defect as caught by the gate `paths`. The case goes into half B of the fixed split of the screen eval, the smaller half, so that no other case moves.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: Refuse a requirement text over the OpenSpec limit (added)
- `roadmap-stage-eval`: The golden set holds the plan with a requirement text over the OpenSpec limit (added)

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/stage/test_roadmap_stage_requirement_length.py`, `tests/roadmap/test_roadmap_plan_check.py`, `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`, `tests/roadmap/stage/test_roadmap_stage_eval_command.py`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, `tests/fixtures/roadmap_eval/stage/3462-a-modified-requirement-over-the-limit/`, `tests/fixtures/roadmap_eval/stage/split.json`, `tests/commands/test_roadmap_eval_screen.py`
- Documents: `docs/roadmap/plan-recheck.md`
- The change fits one pull request.

## Feasibility

- OpenSpec 1.14.3, the version that the tools lock pins, sets `MAX_REQUIREMENT_TEXT_LENGTH = 500` in `dist/core/validation/constants.js`. `validateSpec` in `dist/core/validation/validator.js:733` gives the warning `REQUIREMENT_TOO_LONG` for each requirement of a spec whose text is longer, and `--strict` makes a warning fail.
- The validation of a change (`validator.js:270`) applies the rule to an ADDED requirement only. Its comment says: "MODIFIED is left alone". The #3462 delta is MODIFIED, so the stage validation and `devops openspec check` pass it.
- OpenSpec measures the body of a requirement with `extractRequirementBody` (`dist/core/parsers/requirement-text.js`): the trimmed lines up to the first scenario, joined by one line break. The stage writer puts the text on one line, so the length is the length of that line, as a JavaScript string.
- On the base, `check_proposal` returns no problem for the stock plan with a MODIFIED requirement text of 543 characters (a run of the gate in this worktree).
- The base replay (`uv run devops roadmap eval stage --replay`) exits 0 with 57 cases and "Defects that a gate judges: 81 of 318 (25%)".

## Existing Tool Considered

OpenSpec owns the rule, and the change does not copy its validator. OpenSpec offers no command that validates a change as the merged spec, and its change validation leaves MODIFIED requirements alone, so the gate adds the one length comparison with the OpenSpec limit in one constant. Cost: about 15k tokens to build, 1k tokens a month to keep and fix, about 2 hours.
