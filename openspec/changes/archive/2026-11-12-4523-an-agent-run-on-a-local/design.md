# Design

## Decisions
- The model that the reply names decides before the asked model. A gateway fallback must price and label the run at the group that answered (#4216): an asked local group that a hosted group answers is hosted, and an asked hosted group that a local group answers is local.
- A name is local when it is in `CONST_AI_GATEWAY_VIRTUAL_MODELS` or starts with `ollama:`. These are the local tiers that `roadmap.implement.ladder` accepts (`RoadmapImplementConfig._check_ladder`).
- Each other name that a reply gives stays hosted, a hosted group of `CONST_AI_GATEWAY_HOSTED_MODELS` included. A hosted group sets no `api_base`, so its header names a deployment model and no backend (#3656).
- When the reply names no model, the asked model decides only when it is a local tier. Otherwise the provider and the server decide. `track_request_spend` already makes an asked hosted group with no reply model the deployment model of the record (#3665).
- `record_run_spend` and the hook of `build_agent` keep the reply model in `served_model`. The record and the price need the group that answered.

## Rejected alternatives
- Remove the rule that a gateway reply with a `served_model` is hosted. A hosted group behind a loopback or cluster gateway host would count as local again: `test_a_gateway_reply_that_names_a_deployment_model_and_no_backend_is_hosted` fails.
- Let the asked tier decide over the reply. A run on `devops-coder` that a hosted group answers would count as local at 0 USD, and the fallback price of #4216 is lost: `test_a_local_group_that_a_hosted_group_answers_is_priced_at_the_hosted_group` fails.
- Clear `served_model` in `record_run_spend` for a local group. The record loses the group that answered, and a hosted group that falls back to a local group stays hosted.
- Treat a LiteLLM Ollama reference (`ollama_chat/<model>`) as local. The issue keeps each unknown deployment model hosted, and the reference names no gateway group. A local fallback whose reply names such a reference is a separate item (#4886).
