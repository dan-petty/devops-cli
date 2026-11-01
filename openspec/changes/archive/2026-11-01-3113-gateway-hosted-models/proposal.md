# Proposal

## Why

Issue #3113: the owner wants `gemini-3.8-flash` and two Claude models as models of the LiteLLM gateway, with their API keys. The gateway routes only to Ollama tiers today. It has no key for a provider, its NetworkPolicy admits only the Ollama pods and DNS, and a test (#795) fails on any other egress rule. The owner chose to widen that policy to public addresses on port 443, to serve the three groups as direct models only (no pool and no fallback), and to serve `claude-sonnet-5-5` and `claude-haiku-5-5`.

## Feasibility

- The cost map of the pinned image (LiteLLM v1.103.0, read from the wheel) lists `gemini/gemini-3.8-flash` with a window of 1048576 and prices of 7.5e-07 and 3.75e-06 per token. It lists no `claude-sonnet-5-5` and no `claude-haiku-5-5`, so those two set their own window and prices. Prices are from the Anthropic pricing page: Sonnet 5.5 is 2 and 10 USD per million tokens; Haiku 5.5 is 0.10 and 0.50 USD up to 100,000 prompt tokens, and 0.50 and 2.50 USD above.
- A LiteLLM `Router` built from the three groups starts with `GEMINI_API_KEY` and `ANTHROPIC_API_KEY` unset. A call to the Gemini group then fails with "Missing Gemini API key". So an optional Secret key keeps the gateway up.
- A mocked call of each group gives the cost that the prices predict (Sonnet 0.00022, Haiku 1.1e-05 and Gemini 8.25e-05 USD for 10 input and 20 output tokens).
- The Anthropic pages for the two models say that `temperature`, `top_p` and `top_k` return a 400 error (Sonnet 5.5) or must be omitted (Haiku 5.5). A `Router` with `drop_params` on and the two groups in the map sends `temperature` and `top_p` to the API. With `additional_drop_params: [temperature, top_p, top_k]` on the deployment, the request body holds neither.
- Sonnet 5.5 returns an error to a forced tool call. LiteLLM v1.103.0 cannot know that for this model, so the README tells a caller to send `auto`. The change does not rewrite `tool_choice`.
- A NetworkPolicy cannot name a host, and kube-router matches an ipBlock against pod addresses. So the rule admits `0.0.0.0/0` on TCP 443 and excludes every private range, the carrier-grade NAT range and the metadata range. The guard test accepts exactly this rule and fails on any other ipBlock.

## Existing Tool Considered

LiteLLM already supports the `gemini` and `anthropic` providers, `os.environ/` key references and `additional_drop_params`. No new tool.

## What Changes

- `k8s/llm/gateway/config.yaml` gets three groups: `gemini-3.8-flash`, `claude-sonnet-5-5` and `claude-haiku-5-5`. No pool, fallback or routing group names them.
- `k8s/llm/gateway/deployment.yaml` reads `GEMINI_API_KEY` and `ANTHROPIC_API_KEY` from optional keys of `llm-gateway-secrets`.
- `k8s/llm/gateway/networkpolicy.yaml` gets one egress rule: public addresses on TCP 443.
- `src/devops_cli/k8s/cluster_secrets.py` gets two optional entries, `gemini-api-key` and `anthropic-api-key`. `src/devops_cli/config/env.py` declares the credentials `gemini.api_key` and `anthropic.api_key`, and `docs/ENV_VARS.md` lists them.
- `k8s/README.md` and `SECURITY.md` (rule 12) describe the groups, the keys and the data rule.
- Tests: the gateway tests read the in-cluster groups apart from the hosted groups; the egress guard accepts the one rule and fails on seven widening edits; a new check holds the rules of the hosted groups and fails on six broken edits.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-gateway-routing`: adds the requirements `Hosted groups call a provider with an optional key`, `A Claude group sets its prices and drops refused parameters`, `The gateway reaches providers on port 443 only` and `Hosted groups join no pool`.

## Impact

- Cluster: the gateway Deployment rolls when Argo CD syncs the new ConfigMap. The gateway then sends requests to Google and Anthropic only when a caller names a hosted group.
- A person must store the keys and push them (task 3.1). Until then a call to a hosted group fails with a missing-key error, and every other group works.
- Cost: each token of a hosted group is billed by its provider.
