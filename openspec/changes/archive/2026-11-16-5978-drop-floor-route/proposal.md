# Proposal: #5978

## Why
The gateway group `deepseek-v4.1-flash-1017` called `openrouter/deepseek/deepseek-v4.1-flash-1017:floor`. The suffix `:floor` sorts the providers by price and makes flex endpoints eligible. On 2026-11-16 the cheapest endpoint was a flex endpoint. The median time to the first token of the group went from about 2 s before 10:00Z to 150 s from 11:00Z to 12:00Z, and no stream gave a first token from 13:00Z to 14:00Z. A probe of the group gave no token in 302.9 s; the same model with no `:floor` answered in 2.0 s. OpenRouter sends the timeout in the stream as code 408, which LiteLLM raises with no fallback (#5965). So every roadmap job of the group failed with the class `provider`. Owner, 2026-11-16: "remove ':floor' suffix for now since we want remove as many causes of service job failure as possible right now". Closes #5978.

## What Changes
- The group `deepseek-v4.1-flash-1017` calls `openrouter/deepseek/deepseek-v4.1-flash-1017`. OpenRouter uses its default routing with the same filters (`quantizations: [fp8]`, `data_collection: deny`).
- The model group alias and `CONST_AI_GATEWAY_HOSTED_MODELS` name no `:floor` route.
- A test fails when a deployment or an alias of the gateway names a `:floor` route.
- The built-in price of the group stays. Its key for the `:floor` route stays, so the spend records of that route keep their price.

## Capabilities
- `ai-spend-pricing`: the example deployment model of the requirement "Every hosted gateway group has a price" names the route with no `:floor`.

## Impact
- Argo CD applies `k8s/llm/gateway/config.yaml` on merge, and the gateway pod restarts on the new ConfigMap. No setting and no Service restart.
- The cost per token can be higher than the flex price. OpenRouter reports the real cost of each call, and a follow-up sets the price of the group from one day of reported cost.

## Feasibility
The OpenRouter documentation (provider selection) says: "`:floor` sorts by price and makes flex service-tier endpoints eligible. It is a superset of `sort: \"price\"`." The endpoints API for the model listed `particle-ai/us/flex` as the cheapest endpoint on 2026-11-16. The gateway metric `litellm_llm_api_time_to_first_token_metric` and the probe above show the delay.

## Existing Tool Considered
OpenRouter provider routing is the tool. `preferred_max_latency` only moves slow endpoints to the end of the list and does not exclude them. `sort: "price"` keeps the price order with no flex endpoints, but default routing also weighs the uptime of each provider. The owner chose to remove `:floor`. Cost: one small configuration change and one test.
