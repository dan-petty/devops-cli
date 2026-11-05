# Design

## The fallback of the task

`AIConfig.for_task` applies the overrides of a parent task first when the task has one, and then its own. The table `_TASK_PARENTS` holds one entry, `stage` to `analysis`.

- Rejected: reuse `ai.tasks.analysis` for the planner. It moves refine, intake and alternatives with the planner.
- Rejected: a top-level `ai.stage_model`. It breaks the per-task pattern of `AITasksConfig` and its variables.

## The spend of a run

- Rejected: read the ledger total. The ledger prices a gateway call from the reply headers, and a pydantic-ai run has none, so the total shows 0 USD for a gateway call of the toolbox (checked with `calculate_request_cost` on 2026-11-05).
- Rejected: read the spend from the gateway. The gateway keeps no record for each run.
- Chosen: sum the tokens that `observe_llm_calls` shows during the run, and price the sum once by model name with the price registry. A model without a price gives a null spend.
