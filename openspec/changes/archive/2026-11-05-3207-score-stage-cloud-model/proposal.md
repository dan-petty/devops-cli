# Proposal

## Why

Issue #3207: the plans of the stage job need rework, and no score from a model that is likely to pass shows the cause.
The planner runs on a small model with tight caps, so a failure could come from the model, the prompt, the caps or the gates.
This change gives the stage job its own model task, makes each eval report state its spend, and records what an acceptable score is and how to find the cheapest model that reaches it.
Cost work (#3066, #3060) waits for the baseline.

## What Changes

- Add the task `ai.tasks.stage`. It sets the model of the stage planner, of the call that splits the groups and of `devops roadmap eval stage`. A field it leaves unset takes the value of `ai.tasks.analysis`.
- The stage job and the eval read the context window of the task `stage`.
- The report of `devops roadmap eval stage` holds the input and output tokens and the spend in USD of the run. The text of the score prints both.
- `docs/ROADMAP_WORKFLOW.md` defines an acceptable stage score and the steps of the baseline run.
- The change is observable (a setting, a variable, a report field and messages), so it carries spec deltas.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-task-models`: add the `stage` task and its fallback to `analysis`.
- `roadmap-stage`: the stage job plans with the model of the task `stage`.
- `roadmap-stage-eval`: the live run uses the task `stage` and reports tokens and spend.

## Impact

- A deployed config that sets nothing for `ai.tasks.stage` keeps the model of `ai.tasks.analysis`, so no live behavior changes.
- Only a person sets `ai.tasks.stage.model` in the deployed config.
- The full paid baseline run is not part of this change. A follow-up issue holds it.

## Feasibility

- #3037 is closed and merged (`ToolboxClient` in `src/devops_cli/roadmap/stage_toolbox.py`, `devops roadmap eval stage` plans with it unless `--no-toolbox`). `devops roadmap eval stage --dry-run` lists the toolbox mode and the gateway.
- `k8s/llm/gateway/config.yaml` serves `claude-sonnet-5-5` and `deepseek-v4.1-flash-1017`. The owner rule of 2026-11-02 limits the cloud comparison to these two models.
- `genai_prices.calc_price` prices `claude-sonnet-5-5` (3.0 USD for 1,000,000 input and 100,000 output tokens). It does not know `deepseek-v4.1-flash-1017`, so the report states a null spend for that model unless a price override exists.
- A live run on 2026-11-05 shows that the toolbox runs. One case with `deepseek-v4.1-flash-1017` made 109,476 input and 1,936 output tokens. A plan run made 2 tool calls in its first request and offered no tool in its second request, because the messages reached the limit of the 65,536 window. A sample of 4 cases with the toolbox gave 430,546 input tokens and 1.07 USD with `claude-sonnet-5-5`. The score of this sample is low for both models (3 of 9 and 2 of 9 known defects avoided), so it is no baseline. The full run (about 9.5 USD) waits for the decision of a person, in a follow-up issue.
- The spend ledger prices a call from the headers of a gateway reply. A pydantic-ai run carries none, so the ledger holds 0 USD for a gateway call of the toolbox. The report therefore sums the tokens that the ledger shows to `observe_llm_calls` and prices the sum by model name with the price registry.

## Existing Tool Considered

The price comes from `genai-prices` through the existing price registry (`get_pricing_registry`), and the calls come from the existing `observe_llm_calls` hook of the spend ledger. The change builds no price table and no counter of its own.
The remaining new code is the `stage` task entry, a fallback table of one line, a 30-line sum of tokens and the documents. Cost: about 40,000 tokens to build and about 10,000 tokens a year to keep.

The change fits in one pull request.
