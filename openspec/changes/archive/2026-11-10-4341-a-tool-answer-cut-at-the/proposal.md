# Proposal: #4341

## Why

A tool answer of the stage planner that passes `CONST_ROADMAP_REFINE_TOOL_MAX_CHARS` is cut in the middle of a line, with no notice. `cut` in `src/devops_cli/roadmap/refine/refine_investigation.py` writes the notice only when the line limit dropped a line. A live plan run of #3387 on 2026-11-10 (58 requests, 79 tool calls) shows the harm: 17 of 79 answers reached the character limit, 11 of them at exactly 8,000 characters with no notice. The `file_symbols` answer for `stage.py` (2,926 lines) and several `read_file` answers were cut silently, and the model then read `stage.py` 9 times with guessed line ranges. Closes #4341.

## What Changes

- `cut` ends an answer at a whole line when the character limit applies, and cuts a single line that is longer than the limit alone.
- `cut` ends every answer that lost text, to either limit, with the notice `(more lines are left out)`.
- The tools of refine, stage and the alternatives check use `cut`, so all of them get the change.
- The change carries a spec delta because the answers of the tools are observable by the model.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A cut tool answer says so

## Impact

- Code: `src/devops_cli/roadmap/refine/refine_investigation.py`
- Tests: `tests/roadmap/stage/test_roadmap_stage_tools.py`
- An answer can be a few characters shorter than before (it ends at a whole line) and 26 characters longer with the notice; the window-fit tests keep their margin.

## Feasibility

- Premise checked in the code at `origin/main` (699026ef): `cut` returns `text if len(kept) == len(lines) else ...`, so a text cut to `max_chars` with all lines kept has no notice. The new tests fail on the base.
- Premise checked in a live trace: `.data/agent/scratch/stageopt/base-3387.json` (not committed) lists 79 calls and the characters of each answer: 11 answers have exactly 8,000 characters and 6 have 8,026 (the line notice added).
- `uv run devops roadmap eval stage --replay` makes no tool call and keeps its result.

## Existing Tool Considered

None covers a 5-line cut of a tool answer; the change edits the existing function. Cost: about 15 000 tokens to build, 2 000 to keep and 1 hour.
