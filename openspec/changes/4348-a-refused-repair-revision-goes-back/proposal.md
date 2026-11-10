# Proposal: #4348

## Why

A repair round of the stage job gets no return when the checks refuse its revision. `_gated` sends a refused first reply back to the model once with the problem. `_repaired` raised the stage error at the first refused revision. A repair run costs 22 to 49 requests and 6 to 10 minutes, and one form fault in its revision, which the model fixes at once when told, threw all of that work away. The revision was also written to no file, so a person could not read the reply that ended the item (#4312).

Closes #4348. The change also fixes #4312 (the refused-reply file holds the refused revision).

## What Changes

- A reply that the checks refuse goes back to the model with its problem up to `CONST_ROADMAP_STAGE_GATE_RETURNS` times. The constant is 1. The first reply and the revision of each repair round use one function, `_Planner._returned`.
- A revision that stays refused is added to the refused replies of the item, with its problem, and `<n>.refused.json` holds it beside the refused replies of the first asks.
- The failure text of a revision names the review round and the gate problem: "The revision after the model review fails its checks, also after a return: ...".
- A revision of a repair round that is a placeholder in every text ends the item at once, as a first reply does.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A refused revision returns, and a revision that stays refused is kept

## Impact

- Code: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/stage/test_roadmap_stage_repair_return.py`, `tests/roadmap/test_roadmap_limit_classes.py`
- A repair round can cost up to one more planner call for each round (two rounds at most) when the checks refuse a revision.

## Feasibility

- Premise checked in the trace of the live run of `devops roadmap stage --plan --item 3387` on 2026-11-10 (scratch, not committed): plan run 24 requests, 41 tool calls; gate return 1 request, 0 calls; review run 33 requests, 63 calls; repair run 22 requests, 33 calls, 348 seconds. The run has no request after the repair run, so the refused revision got no return. The traceback ends in `_repaired` at the `raise _stage_error` line, and the failure text is "Scenario 'The plan is on the default branch and the branch is gone' names `stage.pr` with no behavior test."
- A gate return in the same trace took one request and no tool call, so a return of a revision is cheap against a repair run.
- `uv run devops roadmap eval stage --replay` reads recorded replies and keeps its result: 81 of 317 defects caught by a gate, 0 missed, 5 of 5 good plans accepted. The change touches no gate.

## Existing Tool Considered

None: it is control flow of the job, and no library covers it. The change reuses the return logic of `_gated` in one function. Cost: about 25 000 tokens to build, 2 000 to keep and 2 hours.
