# Task 458: Gateway-Routed Reviews and Embeddings Across Every Inference Backend

**Issue**: [#458](https://github.com/dan-petty/devops-cli/issues/458)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p2-medium`
**Scope**: `type/feature`, `scope/ai`, `scope/review`, `priority/p2-medium`

---

## 1. Description & Objectives

The LiteLLM gateway fronts both vLLM and Ollama, yet devops-cli could not use it as the single
router. A review sends every LLM call through one client bound to one provider and model;
embeddings only spoke to Ollama URLs; and review prompts were too large for most servers.

Two prompt-size defects kept small-window servers out of reviews entirely:

- Review pages were `max(128_000, context_window * 3.5)` characters: never smaller than 128K
  characters, which already exceeds the default 32K-token window, so Ollama silently truncated
  pages under the default configuration.
- Persona agents are cached across files and resent their whole memory (up to 96K characters)
  with every page; parallel file workers shared that memory, so one file's prompt could carry
  another file's text.

### Key Deliverables Completed:

- [x] **`devops-review` Gateway Pool**: one virtual model whose deployments cover both vLLM
  profiles and the Ollama nodes, least-busy routed with per-deployment `max_parallel_requests`
  and `max_input_tokens` so pre-call checks keep a prompt off a deployment it would overflow.
- [x] **`ollama/*` Pass-Through**: any Ollama model by name for chat and embeddings, via Ollama's
  OpenAI-compatible API (LiteLLM's `ollama_chat` provider has no embeddings endpoint).
- [x] **Window-Sized Review Pages** (`review_page_chars`): 60% of the analysis context window at
  3.5 characters per token, bounded by an 8K-character floor and the historical 128K cap.
- [x] **Per-Page Persona Isolation**: `MultiAgentPipeline.run`/`run_parallel` accept
  `message_history`; the review passes `[]`, so each page carries only its own prompt.
- [x] **Gateway Embeddings**: `EmbeddingsEngine` routes provider `gateway` through the
  OpenAI-compatible path, preferring the embedding task's own `api_base_url`, then
  `gateway_url`, never a global `api_base_url` meant for another provider; model names pass
  through unchanged.
- [x] **Gateway Hygiene**: `LITELLM_LOCAL_MODEL_COST_MAP=True`, since the gateway's egress is
  limited to the inference backends and the remote cost-map fetch only delayed startup.
- [x] **Automated Tests & Quality Gates**:
  - `tests/test_k8s_llm_gateway.py`: pool deployments, caps and windows against each backend's
    configured context, pass-through target.
  - `tests/test_review_pipeline.py`: page sizing bounds; page steps pass an empty history.
  - `tests/test_agent.py`: an empty history sends only the current prompt.
  - `tests/test_rag_embeddings.py`: gateway URL precedence and unchanged model names.
  - Cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

## 2. Verification on a Live Cluster

An all-persona `devops ai review path` over 15 Ansible playbooks, with the analysis task on
`devops-review` and a 16K window, completed in 3.5 minutes (60 candidate findings, 16 reported).
Requests per backend during the run: single-GPU vLLM 49, dual-GPU vLLM 23, Ollama 15 + 0. The
16K-window server took the largest share, which the 128K-character page floor had made impossible.
Gateway embeddings through `ollama/embeddinggemma:300m` returned 768-dimension vectors, and chat
through `ollama/gpt-oss:20b` answered.

## 3. Remaining Work (tracked in `docs/ROADMAP.md`)

- The second Ollama node received no requests: the `ollama` Service balances per TCP connection
  and LiteLLM keeps its connection open, so all Ollama traffic follows one pod. The gateway needs a
  per-node address for each Ollama pod, which the DaemonSet does not provide.
- File workers are sized from `len(ollama_urls) * ollama_max_parallel`, which has no meaning for
  provider `gateway`.
