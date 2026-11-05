# Proposal

## Why

Issue #3690: the host of the Ollama tier `ollama-16gib` is unstable. It rebooted several times on 2026-11-05, and a person cordoned it. A cordon does not stop a DaemonSet pod, so the gateway continues to route requests to the tier, and those requests fail when the host goes down.

## What Changes

- `k8s/README.md` marks `ollama-16gib` as not serving, and says that the cause is an unstable host.
- `k8s/llm/gateway/config.yaml` has no deployment on `ollama-16gib-fast`: the `devops-review` deployment of `gpt-oss:20b`, the pinned group `gpt-oss:20b` and the order 2 deployment of `qwen3-embedding:0.6b` are deleted. No fallback named those groups.
- `DEFAULT_GATEWAY_REVIEW_SLOTS` has two tiers, so `DEFAULT_GATEWAY_REVIEW_CONCURRENCY` is 2.
- The devcontainer names `ollama-48gib` and `qwen3.8:27b`, the one model of that tier.
- The gateway routes of `gpu_matrix.json` do not name the tier. The hardware profiles and Service aliases of the matrix stay. A test now reads these routes as an Ollama consumer.
- The DaemonSet `ollama-16gib` and its Services stay. The DaemonSet sets `OLLAMA_MAX_LOADED_MODELS` to 1, because the rule that a tier keeps one model allows two only for a chat tier that the gateway sends embeddings to.
- This change alters manifests and the gateway routes, so it carries a spec delta.
- This change fits in one pull request.

**The worst loss.** The review pool has 2 slots, not 3. Embeddings have no third fallback: when both deployments of order 1 fail, an embedding call fails, because the tiers `ollama-48gib` and `ollama-64gib` hold no embedding model (#3567). A review cannot pin `gpt-oss:20b` until the tier returns.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-gateway-routing`: the gateway sends the 16 GiB tier nothing, and the embedding group has its order 1 deployments alone.

## Impact

- Cluster: Argo CD applies the change when it syncs the merge. It rolls the gateway, and it restarts the pod `ollama-16gib` one time, because the env of the DaemonSet changes. The pod then gets no request from the gateway.
- Clients: the model name `gpt-oss:20b` is no longer a gateway model. Each review prompt up to 262,144 tokens fits both deployments of the pool.
- Code: `src/devops_cli/config/defaults.py`, `src/devops_cli/k8s/gpu_matrix.json`.
- Manifests: `k8s/llm/gateway/config.yaml`, `k8s/llm/profiles/ollama-profiles.yaml`.
- Documents: `k8s/README.md`, `k8s/llm/profiles/README.md`, `docs/SELF_IMPROVEMENT.md`, the Ollama knowledge base.
- A revert of this change brings the tier back.

## Feasibility

Checked on 2026-11-05, read-only:

- `kubectl -n llm get ds`: `ollama-16gib` has 1 pod ready on the cordoned node, so the cordon did not stop it. `ollama-24gib-embed-gpu0`, `ollama-24gib-embed-gpu1`, `ollama-48gib` and `ollama-64gib` each have 1 pod ready, so the embedding group keeps its two order 1 deployments and the pool keeps two tiers.
- `test_every_ollama_consumer_names_a_service_that_selects_a_serving_tier` with the tier marked `no` names the three consumers: the gateway config, `DEFAULT_GATEWAY_REVIEW_SLOTS` and the devcontainer.
- `router_settings.fallbacks` in the gateway config names no deleted group, and `git grep` finds `gpt-oss:20b` in no manifest of `k8s/devops` and in no monitoring rule. The local `config.yaml` and the ConfigMaps of the cluster name the model or the tier only in the gateway ConfigMap, which this change replaces.
- The windows of `devops-review` and `devops-background` are all 262144, and the pre-call check reads them, so the pool takes each prompt up to its window.
- `devops ai gateway render` writes no change: the rendered regions hold only the order 1 embedding deployments.

## Existing Tool Considered

The LiteLLM `model_list` and `order` setting cover the need: a deployment that the list does not name gets no request. This change builds nothing. It deletes three deployments, one slot and the matching routes of the GPU matrix.
