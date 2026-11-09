# Proposal: A Claude group answers the stage planner, and a fallback shows

## Why

Issue #4205, defect A of the root-cause run of 2026-11-09. The stage slot of the analysis names `claude-sonnet-5-5`, but DeepSeek answers it. The planner is a pydantic-ai agent with a tool output (`output_type=StageProposal`). With a tool output and no text output, pydantic-ai sends `tool_choice: "required"`. Sonnet 5.5 refuses that with a 400 (`tool_choice: type tool and any are not supported for this model`). The gateway fallback `claude-sonnet-5-5 -> deepseek-v4.1-flash-1017` hides the 400 and returns the DeepSeek reply. The run, its spend record and its metrics all name the asked model, so nothing shows that another model answered.

Two defects follow:

1. The bridge does not tell pydantic-ai that a Claude group of the gateway takes no forced tool choice.
2. A run records the asked model only. A slot can read Sonnet while DeepSeek answers, with no sign in the ledger or in the metrics.

## What Changes

- `resolve_pydantic_ai_model` builds the model of a Claude group on a gateway (target `claude-*`) with the model profile `supports_forced_tool_choice=False`. The agent then sends `tool_choice: "auto"` and keeps the tool list, so Sonnet 5.5 answers with a tool call. Other models keep the default profile and the forced `required`.
- `record_run_spend` reads the model name of each reply (`ModelResponse.model_name`, the `model` field of the gateway reply). It stores it in the `served_model` column of the spend record, and adds to a new counter `devops_cli_ai_model_answers_total` with the labels `asked`, `answered` and `fallback`. `fallback` is `true` when the answered model is not the asked model, after the removal of a provider prefix such as `ollama_chat/`.
- The gateway fallback is not changed. A person decides that.
- No new setting, so no ConfigMap rollout.
- Observable behavior: the request body that the CLI sends to the gateway, a ledger column value and a metric. The change carries spec deltas for both.

## Capabilities

- `ai-structured-reply-constraint` (ADDED): the tool choice that an agent with a tool output sends to a Claude group.
- `ai-spend-pricing` (ADDED): the record and the count of the model that answered.

## Impact

- `src/devops_cli/ai/pydantic_ai_bridge.py`: the Claude branch of `_resolve_remote_inferred_model`.
- `src/devops_cli/roadmap/agent_run.py`: `record_run_spend`.
- `src/devops_cli/telemetry/instruments.py`: one new `Instrument`. The telemetry docs and the instrument tests list it.
- Series count of the new counter: one series for each pair of asked and answered model. The gateway config `k8s/llm/gateway/config.yaml` holds 11 chat groups (12 `model_name` values less the embedding group) and 6 fallback rules. A group that answers as itself adds 1 series, so 11 at most. The 6 rules give 7 fallback pairs at most (`devops-review` reaches `devops-background` and, through it, `qwen3.8:27b`). The bound is 18 series. The stage slots use 4 groups or fewer, so the normal count is 4 to 8. The census command is in the first task group.
- Roadmap Jobs that run the planner on a Claude group call the model that the slot names.
- One fix pull request, so it fits one pull request.

## Feasibility

Checked in the Prepare stage against pydantic-ai 2.59.0 source and against the live gateway:

- `pydantic_ai/models/_tool_choice.py`, `resolve_tool_choice` returns `required` when the agent has an output tool and allows no text output. `OpenAIChatModel._get_tool_choice` sends `required` unless the profile key `supports_forced_tool_choice` is False. Then it sends `auto` and keeps the tool list.
- The field that the issue names, `openai_supports_tool_choice_required`, is deprecated in 2.59.0 and raises `PydanticAIDeprecationWarning`. The change uses the key `supports_forced_tool_choice`, in the `profile` argument of the public `OpenAIChatModel` constructor.
- An offline run of `OpenAIChatModel("claude-sonnet-5-5")._get_tool_choice` with one output tool gave `required` with the default profile, and `auto` with `{"supports_forced_tool_choice": False}`, with `final_result` still offered.
- Live proof by the owner (issue comment 6732771723): `required` gives the 400, `auto` gives a tool call (`final_result`).
- `ModelResponse.model_name` is `response.model` in `pydantic_ai/models/openai.py`. The ledger column `served_model` exists, and the pricing already prices by it.
- Not yet verified: the exact form of `response.model` from the gateway (a provider prefix or a date suffix). The Publish stage makes one live call (cap 1 USD) and records the form in the pull request comment. The tests use a provider prefix as the recorded form (the local ledger shows `ollama_chat/qwen3-coder:30b` for `qwen3-coder:30b`) and one explicit fallback.

## Existing Tool Considered

pydantic-ai covers the need: its model profile is the open, maintained switch for the tool choice, and its `ModelResponse.model_name` carries the answered model. The change adds no home-grown tool-choice code and no patch of the library. The counter uses the existing OpenTelemetry `emit` path. The change deletes no internal code.
