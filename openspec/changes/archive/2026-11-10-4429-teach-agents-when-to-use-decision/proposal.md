# Proposal: #4429

## Why

An agent or a service operator has no guidance that separates a decision model from a generative model. The `ask-jev` skill says how to run the command, but not which kind of model fits a task. `AGENTS.md` only limits the rate of `devops ai` calls. The example configurations name chat models only. An operator can therefore put a chat model where a workflow expects a decision model, or ask Jev to write text.

## What Changes

- Rule 13 of `AGENTS.md` tells an agent to use a decision model for a closed choice and a generative model for text. It links the `ask-jev` skill.
- The `ask-jev` skill in the three skill trees gains a comparison table, the tasks for each model kind, the rule for another decision model and the separate settings.
- `config.example.yaml`, `k8s/devops/configmap.example.yaml` and `k8s/llm/gateway/config.yaml` state that the two model kinds are separate and how a workflow names a decision model.

## Capabilities

The change adds the capability `agent-instructions`. It changes no behavior.

## Impact

Agents and operators get the same rule on when to use each model kind. No setting, command or runtime path changes. The three skill copies stay identical.

## Feasibility

The command `devops ai ask-jev` exists, and `tests/commands/test_ai_ask_jev.py` covers it. `src/devops_cli/ai/pydantic_ai_bridge.py` accepts the `typesafe:` and `system-one:` prefixes for a `DecisionModel`. ADR 0019 and ADR 0020 define the rules of a decision step and a decision point. The change edits documents and comments only, so no runtime path changes.

## Existing Tool Considered

The change uses the existing `ask-jev` command, the `ai_ask_jev` MCP tool and the `pydantic_ai` `DecisionModel`. It builds no client and no new command. Cost: about 6,000 input tokens and 2,000 output tokens, and less than one hour.
