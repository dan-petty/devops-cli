# Design

## Decisions

- **Extend `InvestigationTools` and call `investigate`.** Refine already runs a pydantic-ai agent with read-only git tools and a budget. `StageTools` adds six tools and keeps `list_files`, `read_file` and `search_code`. `investigate` gets optional `limits`, `output_retries` and `trace`, and keeps its defaults for refine.
- **Read the commit through git, with no scratch copy.** The tools run `git` on the staged commit of the clone the job already has. No tool writes. A worktree or a clone would give no gain and would cost time.
- **Implement `StageClient` with a `ToolboxClient`.** `_Planner`, `RecordingClient`, the gates and the golden-set run keep their code. `plan_stage` and `plan_item` take an `investigator` model. Without it the planner makes the one call of today, which `--no-toolbox` and the tests use.
- **Set the budget to 30 tool calls and 50000 output tokens, as constants.** The values come from the refined design of #3037. A call limit bounds the round trips, and a token limit bounds the reply. The request limit is 40 (`CONST_ROADMAP_STAGE_MAX_REQUESTS`). The budgets of refine are constants as well.
- **Set the budget for each plan run, not for each item.** `_Planner.plan` asks the model for a plan, and asks again once when the checks refuse the reply (`stage.py`, `_Planner.plan`). Each ask is one `chat_structured` call, and `ToolboxClient` makes one `investigate` call with new `UsageLimits` for each of them. So one item can use two plan runs: 60 tool calls and 100000 output tokens at most. A shared budget for the item would need state in the client, and the second run needs tools to check the paths that the checks refused. The call that splits the groups (`StageSplit`) goes to the inner client with no tool, so it has no tool budget. A run that passes its limit fails the item, also when it is the second run.
- **Report all plan runs of an item in the comment.** `ToolboxClient` keeps one `RunTrace` for each run. `_Planner.plan` clears them when an item starts and reads all of them at the end. The comment lists the tool calls of the runs in order, and sums the requests and the tokens. The reader sees the full cost of the item, also when the first plan was refused.
- **Keep the hook `_within_budget` of refine.** It takes the tools away when fewer than 4 calls are left, so the model gives its plan instead of a last call. With 30 calls and one call a turn, at most 27 calls run. `tool_calls_limit` ends a run only when one reply holds more calls than are left. A model that calls a tool after the hook took them away ends the run with a tool retry error, and that error names no limit. The spec and the tests state this. An own hook for the stage run would keep the tools until the limit, but it adds code, and the model gains nothing from a last call.
- **Give the symbols of one file, not the AST graph.** The graph takes 110 s for 52 files. Tree-sitter takes 0.04 s for one file.
- **Find the callers with `git grep`.** It covers the whole commit in one call, and it uses the rule of the graph: a name followed by `(`.
- **Map the retries of a reply to the retries of the agent.** `chat_structured` gets `max_retries`. The client passes it as `output_retries`, so a reply that breaks the schema goes back once, as the base spec says.
- **Report the plan run in the comment of the staged item.** The comment already lists the groups. The trace is a few lines more. The full trace of every run is #3032.
- **Map a stopped run to `RoadmapStageError`.** The job already fails an item with that class and shows its masked message in `StageFailure.reason`. The other items are still planned.

## Rejected alternatives

- **A new agent loop in `stage_tools.py`.** `investigate` does the same work, with the same limits and the same errors. A second loop would copy about 100 lines.
- **A scratch clone or a git worktree for the tools.** `git grep`, `git ls-tree` and `git show` read the commit directly, as refine does (`refine_investigation.py`). A copy gives no gain when no tool writes.
- **The whole `CodeGraphBuilder` as a tool.** Measured at 110 s for 52 files and 19.2 s for 20 files.
- **Settings for the budget.** No criterion asks for them. They need a schema entry, a variable, a default and documents, and the budgets of the other agent runs are constants.
- **A flag that turns the toolbox off in the production job.** The job always plans with the toolbox. Only the eval and the tests plan without it, so the A1 score has a baseline.
- **The full trace of #3032 in this change.** That issue is open and has its own criteria. This change keeps only the calls and the tokens of the plan run.
