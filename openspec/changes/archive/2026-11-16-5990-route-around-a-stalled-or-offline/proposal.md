# Proposal: #5990

## Why
On 2026-11-16 from about 10:00Z, `openrouter/deepseek/deepseek-v4.1-flash-1017` waited about 300 s for its first token on OpenRouter, for more than 5 hours. OpenRouter then sent a 408 inside the stream, and LiteLLM 1.103.11 raises such an error with no retry and no fallback. The router counted no failures, because `allowed_fails: 3` is the LiteLLM default, so the group never cooled, and the gateway ran no health check. Every DeepSeek job call failed until a person moved the jobs to `deepseek-v4.1-flash` (#5988). This change is step 1 of the build plan in the design comment of #5990, which names #5990 for this step. Closes #5990. The later steps (alerts, a client first-token deadline, LiteLLM 1.109.1, an upstream LiteLLM change, and #5967) need issues of their own.

## What Changes
- The group `deepseek-v4.1-flash-1017` gets two deployments. Order 1 calls the dated model with `allowed_fails: 0`, `cooldown_time: 120` and `health_check_timeout: 30`. Order 2 calls `openrouter/deepseek/deepseek-v4.1-flash` with `health_check_timeout: 30`. Both keep the fp8 and `data_collection: deny` filters, the window and `supports_response_schema`. The group `deepseek-v4.1-flash` stays, with `health_check_timeout: 30`.
- `router_settings.allowed_fails` goes from 3 to 2.
- `general_settings` turns on background health checks every 60 s with health-check routing, for the two DeepSeek groups only.
- The fallback `deepseek-v4.1-flash-1017` to `deepseek-v4.1-flash` stays: it answers a call while both deployments of the group are cooled.
- The template `k8s/devops/configmap.example.yaml` names `openrouter/deepseek/deepseek-v4.1-flash-1017` again for `ai.model`, each DeepSeek task and the implement ladder. This reverses the manual choice of #5988, because the group now routes around a stall itself.
- The price test checks each deployment. The comments of `_HOSTED_GROUP_PRICES`, both YAML files, `k8s/README.md` and `docs/CLUSTER.md` item 19 tell the new routing.

## Capabilities
- `ai-gateway-routing`: the DeepSeek group requirement and the hosted-group requirement change; two requirements are new (health checks, router `allowed_fails`).
- `roadmap-service-deployment`: three requirements name `deepseek-v4.1-flash-1017` again.
- `ai-spend-pricing`: two requirements price each deployment of a group.

## Impact
- Rollout: after the merge, Argo CD applies `k8s/llm/gateway/config.yaml` (the ConfigMap hash rolls the gateway). Then a person runs `devops k8s deploy-stack --stack devops` for the template; the settings reload for each round. Apply the gateway first: a template that names -1017 on the old gateway has no order 2.
- Cost: 3 health-check calls a minute, at most about 0.12 USD a day. While order 2 answers, a call costs 4 to 5 times more.
- A call in flight when a stall begins still fails after the stall (about 300 s); the client sends it again (#5965), and the new send gets order 2.
- A run of an agent that order 2 answers records the price of order 1: the reply body names the group. The gateway spend is right for each deployment.

## Feasibility
Each key exists in LiteLLM 1.103.11: `background_health_checks`, `health_check_interval`, `enable_health_check_routing` and `background_health_check_model_groups` (`proxy/proxy_server.py:6408-6457`), `model_info.health_check_timeout` (`proxy/health_check.py:528`), the deployment `allowed_fails` and `cooldown_time` (`router_utils/cooldown_handlers.py:96-176`, `router.py:8206-8227`), `order` (`router.py:12905`), and the default `allowed_fails` 3 (`constants.py:76`). A mock provider drove the router and the proxy of 1.103.11 with this config: an in-stream 408 on order 1 sent the next call to order 2 in 0.010 s, a stalled health check took order 1 out 83.5 s into the stall with no failed call, and order 1 got its calls back 61.7 s after it recovered.

## Existing Tool Considered
LiteLLM deployment `order`, deployment `allowed_fails` and `cooldown_time`, background health checks with health-check routing, and router fallbacks do this step. The change is configuration and tests only; nothing is built. A first-token deadline is not in LiteLLM 1.103.11; the later steps of #5990 add it.
