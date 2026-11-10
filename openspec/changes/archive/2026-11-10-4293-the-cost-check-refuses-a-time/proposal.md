# Proposal: #4293

## Why

The cost check of the stage job refuses a plan that gives its cost (#4293). `_TIME_COST` in `src/devops_cli/roadmap/stage/stage_change.py` reads a time only as a digit and the unit `hours` or `minutes`. A plan that states the elapsed time in days or weeks, or with a number word, gets "builds_own is true, and existing_tool gives no cost". Rule 3 of `AGENTS.md` asks for "elapsed time" and names no unit. A live stage run on #3599 with the live stage model refused a first reply whose `existing_tool` said "about 45k tokens to build, about 8k tokens each month to keep and fix, and about two days of elapsed time".

## What Changes

- Read a time in minutes, hours, days or weeks, with a digit or a number word from one to twelve (`a`, `an`), in `_TIME_COST` of `src/devops_cli/roadmap/stage/stage_change.py`.
- The change carries a spec delta because it changes which plans the stage job refuses.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A build cost states its time in minutes, hours, days or weeks

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_change.py`
- Tests: `tests/roadmap/stage/test_roadmap_stage_cost_units.py`

## Feasibility

- The cause is in the code: `_TIME_COST` in `src/devops_cli/roadmap/stage/stage_change.py` matched `\d+ (hours|minutes)` only, and the reply of the live run held "about two days of elapsed time".
- The reply is kept in the refused-reply file of the run: the first refused reply of #3599 holds `existing_tool` with "Written cost: about 45k tokens to build, about 8k tokens each month to keep and fix, and about two days of elapsed time."
- First check against the real system: `uv run devops roadmap eval stage --replay`, which must keep its verdict on every case.
- Second check: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_cost_units.py tests/roadmap/stage/test_roadmap_stage_content.py`.

## Existing Tool Considered

No installed library reads an amount of work in words and units, and the project holds no such helper. The change adds the units `days` and `weeks` and a list of twelve number words to one pattern; the cost is about 10k tokens to build, 2k tokens to keep and 30 minutes. The change deletes no internal code.
