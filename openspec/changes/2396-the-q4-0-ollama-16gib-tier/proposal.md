# Proposal

## Why

#2396 reports that the ollama-16gib tier uses a q4_0 KV cache while all other tiers use q8_0. Ollama passes the value to llama-server for every model, including the embedding model. The 4-bit cache changes the vectors of qwen3-embedding:0.6b, so a RAG batch routed to the 16gib tier as an order-2 fallback puts drifted vectors into the shared Qdrant collection and degrades retrieval.

## What Changes

- Change OLLAMA_KV_CACHE_TYPE from q4_0 to q8_0 in the ollama-16gib DaemonSet env block in k8s/llm/profiles/ollama-profiles.yaml.
- Update the file header comment that references q4_0 KV cache to reference q8_0.
- Add a spec requirement that all Ollama tiers in the embedding group use the same KV cache type.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-gateway-routing`: uniform-kv-cache-type

## Impact

- Code: `k8s/llm/profiles/ollama-profiles.yaml`

## Feasibility

- The premise is confirmed: line 126 of k8s/llm/profiles/ollama-profiles.yaml shows value: q4_0 for ollama-16gib, while lines 271, 411, 558, 707 and the remaining tiers show value: q8_0.
- The gateway config at k8s/llm/gateway/config.yaml lists ollama-16gib-fast as an order-2 deployment of qwen3-embedding:0.6b, confirming the fallback path.
- The archived change openspec/changes/archive/2026-10-28-2395-ollama-0-40-12/design.md explicitly defers this fix to #2396.
- First check: grep for OLLAMA_KV_CACHE_TYPE in k8s/llm/profiles/ollama-profiles.yaml and confirm every occurrence has the value q8_0.
- Second check: parse the YAML and assert that every DaemonSet container env block sets OLLAMA_KV_CACHE_TYPE to q8_0.

## Existing Tool Considered

Not applicable. This is a one-line configuration change to an existing Kubernetes manifest. No external tool or library covers the need.
