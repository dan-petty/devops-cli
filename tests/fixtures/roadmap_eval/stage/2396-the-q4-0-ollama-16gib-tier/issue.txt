### Problem Description

`ollama-16gib` sets `OLLAMA_KV_CACHE_TYPE: q4_0`. The other eight tiers set `q8_0` (`k8s/llm/profiles/ollama-profiles.yaml`). Ollama passes the value to `llama-server` for every model, also for the embedding model (`--cache-type-k q4_0 --cache-type-v q4_0`). The 4-bit KV cache changes the vectors of `qwen3-embedding:0.6b`: for the same input, a vector from `ollama-16gib` has a cosine of 0.78 to 0.92 against a vector from a `q8_0` tier.

The gateway lists `ollama-16gib-fast` as an `order: 2` deployment of `qwen3-embedding:0.6b` (`k8s/llm/gateway/config.yaml`). When an order-1 tier fails or cools down, a RAG batch goes to it. Its vectors then go into the same Qdrant collection as the `q8_0` vectors, and retrieval of those chunks gets worse. Nothing records which tier made a vector.

### Reproduction Steps

1. Make sure that `ollama-16gib` has no model loaded (`kubectl -n llm exec ds/ollama-16gib -c ollama -- ollama ps`), so the test evicts nothing.
2. Port-forward `ds/ollama-16gib` and `ds/ollama-48gib-slow`.
3. Send the same `/api/embed` request to each: `{"model": "qwen3-embedding:0.6b", "input": [<three texts>], "options": {"num_ctx": 8192}}`.
4. Compute the cosine of each pair of vectors.

### Expected vs Actual Behavior

- Expected: every tier that serves the embedding group makes the same vector for the same input (cosine 0.999 or more, the noise between two GPU families).
- Actual: on 2026-10-28, with Ollama 0.34.4, three texts gave cosines of 0.858, 0.922 and 0.784 between `ollama-16gib` (`q4_0`) and `ollama-48gib-slow` (`q8_0`). On Ollama 0.40.12, with the KV cache type equal, the same comparison across two GPU families gave 0.9995 to 0.9997, so the KV cache type causes the difference.

### Environment Diagnostics

- Ollama 0.34.4 on every tier. 0.40.12 passes `OLLAMA_KV_CACHE_TYPE` to `llama-server` in the same way (`llm/server.go`, `llm/llama_server.go`).
- `qwen3-embedding:0.6b`, Q8_0 GGUF, last-token pooling.

### Logs, Traces, or Terminal Output

`llama-server` command on the `q8_0` tier: `--cache-type-k q8_0 --cache-type-v q8_0 --flash-attn auto --embedding -b 2048 -ub 2048`. On a `q4_0` tier the same command has `--cache-type-k q4_0 --cache-type-v q4_0`.

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=bb46660c8d12e28520a25e8171ec300c627df0db -->
## Proposed design

### Problem statement
The ollama-16gib tier sets OLLAMA_KV_CACHE_TYPE to q4_0 while the other eight tiers set q8_0. Ollama passes this value to llama-server for every model, including the embedding model. The 4-bit KV cache changes the vectors of qwen3-embedding:0.6b, so a vector from the 16gib tier has a cosine of 0.78 to 0.92 against a vector from a q8_0 tier. When the gateway routes a RAG embedding batch to the 16gib tier as an order-2 fallback, the drifted vectors enter the shared Qdrant collection and degrade retrieval quality for those chunks.

### Acceptance criteria
- Criterion 1: The ollama-16gib DaemonSet in k8s/llm/profiles/ollama-profiles.yaml sets OLLAMA_KV_CACHE_TYPE to q8_0.
  Verification: Read the ollama-16gib container env block in k8s/llm/profiles/ollama-profiles.yaml and confirm the value is q8_0.
- Criterion 2: All nine Ollama tiers in ollama-profiles.yaml use the same OLLAMA_KV_CACHE_TYPE value.
  Verification: Grep for OLLAMA_KV_CACHE_TYPE in k8s/llm/profiles/ollama-profiles.yaml and confirm every occurrence has the value q8_0.
- Criterion 3: After the change, the same /api/embed request sent to ollama-16gib and ollama-48gib-slow returns vectors with a cosine similarity of 0.999 or higher.
  Verification: Port-forward both DaemonSets, send the same three-text embedding request to each, and compute the pairwise cosine. Every pair must be 0.999 or above.

### Key questions
- **Will the 16gib tier have enough VRAM for a q8_0 KV cache with its 48000-token context and two loaded models?**: Yes. The 16gib tier uses a shorter context (48000) than the other embedding tiers (128000 or more), and the issue and intake both treat the one-line change as safe. The knowledge base document confirms q4_0 saves roughly 50% of per-slot VRAM, so q8_0 uses more, but the shorter context and the tier's 16-to-20 GiB GPU target absorb the difference. (proposed) [sources: k8s/llm/profiles/ollama-profiles.yaml:117, src/devops_cli/ai/knowledge_base/it_domains/tools/ollama.md:31, openspec/changes/archive/2026-10-28-2395-ollama-0-40-12/design.md:16]
- **Should the fix also add metadata to record which tier produced each vector in the Qdrant collection?**: No. The intake scopes this item to the one-line config fix. Recording the producing tier is a separate concern and is not part of this change. (proposed) [sources: k8s/llm/gateway/config.yaml]

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
None.
<!-- devops-roadmap-refine:end -->

<!-- devops-roadmap-record {"Effort": "Low", "Owner": null, "Priority": "P2-Medium", "Status": "Blocked", "Value": "Medium", "implement.branch": "fix/2396-the-q4-0-ollama-16gib-tier", "implement.job": "devops-cli-runner-20261101-142549-17db", "implement.job_digest": "sha256:04d655904252706a7321aed38fa5cafd293625c5db469f252f57163a7c463f16", "implement.job_state": "succeeded", "implement.spend": "{\"requests\": 22, \"input_tokens\": 478637, \"output_tokens\": 2696}", "implement.stopped": "group 1", "refine.block_paths": null, "refine.blocked_by": null, "refine.body_hash": "626b04208ab7869817c281415eb6274f61d7452168ebdf2c7ff84351ecdb09e8", "refine.failed_body_hash": null, "refine.needs_split": "false", "refine.next_step": "ready", "refine.section_hash": "47c42321d71f340ddf86ff14066f06a57174b928422cdd2b3d30f422121250ce", "stage.branch": "fix/2396-the-q4-0-ollama-16gib-tier", "stage.file_cap": null, "stage.groups": "[[\"Set q8_0 KV cache on ollama-16gib\", 3007]]", "stage.needs_split": null, "stage.pr": "2988", "stage.ready": "2988", "stage.sha": "29030e3780befb46b220289621d7f231d018d738"} -->
