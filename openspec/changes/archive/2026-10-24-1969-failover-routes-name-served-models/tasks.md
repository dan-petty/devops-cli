# Tasks

## 1. Routes name served models

- [x] 1.1 Write `test_every_gateway_route_and_failover_route_names_a_model_that_its_tier_serves` and its negative control in `tests/test_k8s_llm_gateway.py`, and verify that `uv run devops ci test tests/test_k8s_llm_gateway.py` fails on the base and names the five routes to `qwen2.5-coder:7b` and `qwen2.5-coder:14b`
- [x] 1.2 Set `DEFAULT_GATEWAY_ROUTES` to the models that the gateway config sends to the default tier, and make a failover to `direct-ollama` keep the model of the default route, and verify that `uv run devops ci test tests/test_k8s_llm_gateway.py tests/test_ai_gateway.py` passes
- [x] 1.3 Make the capability gate tests write a route table with a small `devops-coder` route, remove `test_default_routes_target_profiles`, and assert the model of the `direct-ollama` failover, and verify that `uv run devops ci test tests/test_ai_gateway.py` passes
- [x] 1.4 Point the Portkey `ollama-coder` target at the `devops-coder` route, bind the two in `tests/test_ai_gateway_portkey.py`, and verify that `uv run devops ci test tests/test_ai_gateway_portkey.py` passes

## Workflow follow-up

- A route table that `devops ai gateway` saved before this change keeps its old routes, because the router loads a saved table in place of the default routes: moved to #2045.
- The Portkey gateway reads its routing config in the documented way, or the unused config goes: moved to #2046.
- The default fallback model and the Open WebUI model list name models that the gateway serves: moved to #2047.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
