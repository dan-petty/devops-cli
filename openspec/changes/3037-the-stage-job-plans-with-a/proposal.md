# Proposal

## Why

The stage job planner makes one model call on a fixed context. It cannot investigate the codebase. 25 of 37 plans name files that do not exist, and 17 ignore code or tests that do exist. #3037 asks for a read-only investigation toolbox with a bounded budget so the planner grounds its plans in the actual code.

## What Changes

- The stage job planner runs an agent loop with read-only tools in a scratch clone.
- The tool set is limited to list files, read file, grep, git log, git show, AST graph, callers of symbol, devops ai repomap, and read base spec.
- A budget of 30 tool calls and 50,000 tokens bounds each plan run.
- The trace records every tool call and the total token count.
- The planner writes the commands it ran and their output into Feasibility.
- The deterministic gates still validate the plan result.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: Planner tool set is read-only, Planner references only existing files, Plan run trace records tool calls, Plan run stops at budget

## Impact

- Code: `src/devops_cli/roadmap/stage_tools.py`, `src/devops_cli/config/constants.py`
- Documents: `CONTEXT.md`
- Tests: `tests/test_roadmap_stage_tools.py`

## Feasibility

- The issue states the premise: 25 of 37 plans name files that do not exist. ADR 0005 confirms the same pattern: a model on a fixed input produced a hallucinated file name (app/shell.py:4) that was VERIFIED in all eleven runs.
- ADR 0005 confirms the sandbox pattern: tools run on a worktree of the reviewed commit, inside the sandbox with no network.
- CONTEXT.md confirms the stage job runs in the model lane and the implement job step infrastructure provides the agent loop.
- First checks: run `uv run devops ci test` to confirm the existing test suite passes. Run `uv run devops ci --only openspec` to confirm the OpenSpec gate passes on the current tree.

## Existing Tool Considered

No external tool covers this need. The project already has the agent loop with tool calling (the implement job step infrastructure). The written cost is the tokens to define the read-only tool schemas, enforce the budget, record the trace, and wire the stage job to the existing loop. No internal code is deleted.
