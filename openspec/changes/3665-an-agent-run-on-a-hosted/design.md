# Design

## Decisions

- **One rule in `track_request_spend`.** The function knows the provider, the asked model, `served_by` and `served_model` of every record. When the provider is `gateway`, `served_by` and `served_model` are empty, and the asked model is in `CONST_AI_GATEWAY_HOSTED_MODELS`, the asked model becomes `served_model`. The price (`is_local`, genai-prices), the `local` label and the stored `served_model` then agree, and the 17 `chat_dispatch` rows with no name get the fix too. `record_run_spend` stays as #4216 made it.
- **A model that a reply names wins.** A run asked for Sonnet that DeepSeek answers is priced as DeepSeek, as the issue requires and as #4216 records it.
- **A local group keeps the local rule.** `devops-coder` and the other local groups are not in the hosted list, so the host rule of `is_local` decides, and the issue requirement "keep the local-host rule" holds. `is_local` is not changed.
- **The tests set the gateway host as the cluster host.** The tests write `k8s.domain` and `ai.gateway_url` as the existing pricing tests do, so the fault shows. A test with the default settings would pass on origin/main for the wrong reason.

## Rejected alternatives

- **The header hook of the issue** (an httpx response hook in `create_pydantic_ai_provider` that reads `x-litellm-model-name`, and a callback to the bridge). Rejected: the task of #3665 of 2026-11-09 asks that the counter prices a hosted group by the asked model when no reply names one, and the hook covers only a reply that carries the header. It also needs a change in `pydantic_ai_bridge.py`, which #4220 changes in parallel.
- **The rule in `record_run_spend` only.** Considered: it fixes the agent runs, and leaves the 17 `chat_dispatch` rows with no name. It is the fallback if a reviewer wants the change in `agent_run.py` only.
- **A change of `is_local` so that a hosted group name decides.** Rejected: `is_local` takes no model, and the issue requires that its decision for a reply that names no model stays.
