# Proposal: #4281

## Why

The trace gate (#3266) refuses a Feasibility sentence that names a tool or a path that the plan runs of this process did not call. A kept plan (#4064) is read from a file, so no plan run of this process made it. The record holds the key, the proposal and the request, and no trace facts. A plan run that follows a hit has only its own calls as facts. This happens when another gate refuses the kept plan on a moved commit and the planner is asked again, and when the model review returns the plan and the planner repairs it. The new reply keeps the claims of the kept plan, and the trace gate refuses it (the live run of item #4062 on 2026-11-09, model `claude-sonnet-5-5`: "names the tool `read_issue`, but the run did not call it"). On a hit, the first reply is not checked at all, because the facts are `None`.

## What Changes

- `StagePlanRecord` gets the field `facts` (`PlanFacts`): the tool names of the plan runs, and the paths that they read and that the Feasibility section of the plan cites. Both are sorted lists. The field defaults to `None`.
- The planner writes the facts with the plan. On a hit, `_trace_facts` joins the kept facts with the facts of each plan run of the item, so the trace gate checks the kept plan and each revision of it.
- A record without `facts` (the old format) still loads. The planner counts it as a miss, deletes the file and plans again. It is not a pass.
- The key is not changed. It holds the model name, the toolset and the prompt version already, so a new planner model gives a new key and a new plan.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: adds the requirements `A kept plan holds the trace facts of its run` and `A kept plan without facts is planned again`.

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_plan_record.py`, `src/devops_cli/roadmap/stage/stage.py`.
- Tests: `tests/roadmap/stage/test_roadmap_stage_plan_record_facts.py`.
- The plan file on the data volume of the Service grows by the tool names (at most the tools of the toolset) and by the paths that the plan cites (at most the paths of its Feasibility text). Files in the old format are planned again once.
- No new setting, no new constant, no metric change (a record without facts counts as `miss`).

## Feasibility

- The premise "a hit has no trace": `_Planner.plan` clears `self._traces`, then `_kept` returns the record and `_gated` runs with `first=kept.proposal`. No plan run happens, so `_trace_facts()` returns `None`. Read in `stage.py` at `origin/main` f3fb5355.
- The premise "a run after a hit has only its own calls": `_trace_facts` joins the plan runs of `self._traces` only. `_gated` (second reply) and `_repaired` (review round) call it after a new plan run. The new test `test_a_revision_of_a_kept_plan_keeps_the_claims_of_the_run_that_made_it` fails on `origin/main` with the trace problem of the live run.
- I did not read the full log of the live run, so the exact refusal path of #4062 is not proven. The two paths above are read in the code, and the tests prove them.
- The key holds the planner model: `PlanFiles.key` passes `settings.ai.for_task("stage").model` to `plan_key`. A new model gives a new key, so a kept plan is not reused after a model change. The new test `test_a_new_planner_model_is_a_miss` proves it.
- Check that fails on `origin/main`: `uv run devops ci fail-to-pass --base origin/main`.

## Existing Tool Considered

`TraceFacts` and `RunTrace.combined` in `src/devops_cli/roadmap/agent_run.py` hold the facts and join runs. The change stores a bounded copy in the existing pydantic record. No new library. To skip the trace gate for a kept plan was rejected: it keeps the unchecked first reply and weakens the gate.
