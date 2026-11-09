# Proposal: #4257

## Why

The trace gate of the stage job compared the Feasibility claims of a reply with the calls of the last agent run only. After the one return of a refused reply, the second run often calls no tool, because the plan holds the facts already. A claim that the first run made true was then refused. The live run on item #4062 lost its plan this way: "The Feasibility section names the tool `read_issue`, but the run did not call it." (#4257).

## What Changes

- `RunTrace` gets a `row` field: the job row of the run. `ToolboxClient` sets it to `PLAN_ROW` for a plan run and to `REVIEW_ROW` for a review run.
- `_Planner._trace_facts` builds the facts from every plan run of the item (`RunTrace.combined`), not from the last run. A review run is not a plan run, so its reads support no claim of the planner.
- The requirements "Feasibility cites only what the plan run did" and "Trace facts of a run" say "the plan runs of the item" where they said "the run that wrote the reply". The change alters what the stage job accepts, so it carries a spec delta.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: the trace gate reads the calls of every plan run of the item.

## Impact

- Code: `src/devops_cli/roadmap/agent_run.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_toolbox.py`
- Tests: `tests/roadmap/stage/test_roadmap_stage_trace_runs.py`, `tests/roadmap/stage/test_roadmap_stage_gates.py`
- The change fits one pull request.

## Feasibility

- I read the code. `ToolboxClient.chat_structured` appends a new `RunTrace` to the shared `traces` list for each plan run and each review run. `_Planner._gated` asks again after a refused reply, and the old `_trace_facts` returned `TraceFacts.of(traces[-1])`, so the facts of the reply after the return held the correcting run only.
- The test `test_a_claim_of_the_first_run_holds_after_the_return` scripts two runs: the first reads the path and its reply is refused for the missing security text, the second calls no tool. On origin/main the item fails with "The Feasibility section states that `src/devops_cli/roadmap/agent_run.py` was read, but the run did not read it." With the change the item passes.
- The golden set of the stage eval replays through the gates: `uv run devops roadmap eval stage --replay` accepts 5 of 5 good plans.

## Existing Tool Considered

`RunTrace.combined` and `TraceFacts.of` already join runs and read facts. No new library and no new helper is needed. The change adds one field and replaces the body of `_trace_facts`. The cost to build is low: about 1 hour of tokens and time.
