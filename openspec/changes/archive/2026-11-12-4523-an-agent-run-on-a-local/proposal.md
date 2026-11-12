# Proposal: #4523

## Why
An agent run on a local gateway group, such as `devops-coder`, records its tokens as hosted (#4523). `record_run_spend` and the hook of `build_agent` send the model name of the reply as `served_model`. That name is the gateway group that answered. `is_local` returns False for each gateway call that has a `served_model` (#3656), so a run on a local group gets `local="false"` on `devops_cli_ai_tokens_total`, the pricing source `unknown` at 0 USD, and the warning for an unpriced hosted model. The AI spend dashboard then leaves these tokens out of the local savings.

## What Changes
- `is_local` takes the asked model in a new `model` argument. For a gateway call that names no backend, the model that the reply names decides, and the asked model decides when the reply names none. A local gateway group (`CONST_AI_GATEWAY_VIRTUAL_MODELS`) or an `ollama:` model is local. Each other model that a reply names, a hosted group included, stays hosted (#3656).
- `calculate_request_cost` gives the asked model to `is_local`. So a run on a local group gets the pricing source `local`, 0 USD, the label `local="true"` and no warning, and a gateway fallback is priced at the group that answered (#4216).
- The change alters what the spend ledger and the token series record, so it has a spec delta.

## Capabilities
- `ai-spend-pricing`: two ADDED requirements. The group that answered decides the locality of a gateway call, and a run on a local group records local tokens.

## Impact
- A workstation `devops roadmap implement` run with the default `roadmap.implement.ladder` (`devops-coder` only) records its tokens as local. The Service ladder names hosted groups only, so the Service records the same as before.
- The lifetime report (`devops ai cost`) reads the ledger rows with the same `is_local` rule, so a stored row whose `served_model` is a local group counts as local.
- No setting, command, message or manifest changes. The change fits one pull request.

## Feasibility
- On `main` (`db4b19a7c`), `is_local(server="llm.example.com:4000", provider="gateway", served_model="devops-coder")` returns False: line 333 of `src/devops_cli/ai/spend/pricing.py` returns False for each gateway call with a `served_model`.
- The reply of an agent run names the group: LiteLLM v1.103.10 (the image of `k8s/llm/gateway/deployment.yaml`) sets the `model` field of a reply to the requested model in `_override_openai_response_model` of `litellm/proxy/common_request_processing.py`. It keeps the model that answered when `x-litellm-attempted-fallbacks` is above 0. The issue records `answered` equal to `asked` on `devops_cli_ai_model_answers_total` for each hosted group that ran in the last 7 days.
- A ladder tier is a local gateway group, a hosted group or an `ollama:` model: `RoadmapImplementConfig._check_ladder` in `src/devops_cli/config/settings.py` refuses each other name.
- The test fakes reproduce the defect with no model call: `record_run_spend` with a `_GatewayModel` on `devops-coder` and a reply that names `devops-coder` records the pricing source `unknown`.

## Existing Tool Considered
No open tool decides whether a gateway group of this project runs on local hardware: the group names live in `src/devops_cli/config/constants.py` and `k8s/llm/gateway/config.yaml`. genai-prices prices models, and LiteLLM names the group, but neither knows where a group runs. The change edits one branch of `is_local` and adds no module. Cost: about 40,000 tokens to build, 5,000 tokens a year to keep, 5,000 tokens to fix, and half an engineer-day. The change deletes the rule that a gateway reply with any `served_model` is hosted (the second `if` of `is_local`).
