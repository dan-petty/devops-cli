# Proposal: #4207

## Why

Since #4195 the stage context holds the failure classes and the runner facts, and the stage job reads their four source files at the staged commit. A golden case of `devops roadmap eval stage` is frozen at an old commit. Most old commits lack `src/devops_cli/roadmap/failure.py` or `src/devops_cli/roadmap/runner_tools.py`. The context builder then raises `RoadmapStageError("Staged source moved or missing: <path>")`, and the live run counts that error as `refused`. So 42 of the 48 cases that the run plans end before any model call, and the baseline of #3566 would score 6 cases. The dry run lists 48 cases because it builds no context, so it hides the fault. Closes #4207.

## What Changes

- `plan_item` takes an optional `facts_source`: a checkout whose files the facts context reads when the staged commit lacks them. The planner passes it to the one reader of `_request`: the staged commit first, then `facts_source` at `HEAD`. The context builder `collect_stage_facts_context` stays the only builder.
- The stage job passes no `facts_source`, so it keeps its loud error when a staged source moves. Product code does not detect the eval: the caller picks the reader through a parameter.
- `run_case` passes the repository of the run as `facts_source`. The facts then describe the runner of today, and the plan of a case reaches the model.
- A file that neither the commit nor the checkout holds still ends the case `refused` and names the path.
- The observable behavior of `devops roadmap eval stage` changes, so the change carries a spec delta in `roadmap-stage-eval`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage-eval`: adds the requirement "The live run reads the runner facts in the checkout".

## Impact

- Code: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_eval_run.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_eval_facts_context.py`

## Feasibility

Checked at `origin/main` d37762b6 (release 0.98.0) with no model call. The golden set holds 55 cases; 48 hold a commit and 7 do not.

- `load_cases` and `cases_with_commit` give 48 cases to run. `collect_stage_facts_context` with the reader of the job (`_read_staged_file` at `case.base_commit`) raises `RoadmapStageError` for 42 of them. The same call with a reader that tries the case commit and then `HEAD` of the repository checkout raises for 0 of 48. The probe is `.data/agent/scratch/premise.py`.
- The new tests confirm the count on the base: `tests/roadmap/stage/test_roadmap_stage_eval_facts_context.py` fails for the three shapes (both files absent, only `runner_tools.py` absent, only `failure.py` absent), and the real-case test names `2116-the-scanner-executor-tests-find-the` as `refused` with "Staged source moved or missing: src/devops_cli/roadmap/failure.py".
- `Stage._request` builds the facts context, `plan_item` runs `_request`, and `run_case` calls `plan_item`, so one parameter reaches the context from the eval.
- No open or merged pull request does the work. #4195 caused the fault.

## Existing Tool Considered

`git show <commit>:<path>` through the existing `_read_staged_file`, and the standard library. No new tool or library is needed: the change passes a different reader to a function that already takes one. The change adds about 15 lines and one test file. Cost: 8,000 tokens to build, 1,000 tokens per month to keep, and two hours. It deletes no internal code.
