# Task 545: Review Load Spreads Across the Whole LLM Pool

**Issue**: [#545](https://github.com/dan-petty/devops-cli/issues/545)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/ai`, `priority/p1-high`
**Pull Request**: [#644](https://github.com/dan-petty/devops-cli/pull/644)

---

## 1. Description & Objectives

During a live review the 32B vLLM was busy in 12 of 13 samples, the 14B vLLM in none and the Ollama nodes in 0 and 1; at a stage's end all four calls sat on one server. Three causes combine. `simple-shuffle` routes by weight (5:3:1:1), not load. Pre-call checks drop the 14B server from prompts over its 12,288-token limit, which numbered pages and whole-file verification reach, sending about 71% to the 32B server. And a review keeps few calls in flight: 4 files at once, a file's pages in sequence, one call at each stage's tail.

#### Key Deliverables:
- [x] Configure dual-GPU vLLM `devops-review` throughput weight to `5` and `max_input_tokens` to `61440` (aligned with 64K context window `--max-model-len 65536`).
- [x] Configure Ollama-2 `devops-review` throughput weight to `1` and `max_input_tokens` to `43904` (aligned with `OLLAMA_CONTEXT_LENGTH: 48000` minus 4K tokens for reply).
- [x] Elevate `devops-reasoning` `max_input_tokens` to `61440` in `k8s/llm/gateway/configmap.yaml` inside the 64K vLLM window.
- [x] Elevate vLLM deployment parameters in `k8s/llm/vllm/deployment.yaml` (`--max-model-len 65536`, `--gpu-memory-utilization 0.95`, `--max-num-seqs 64`).
- [x] Update documentation in `k8s/README.md` to reflect `qwen3-coder:30b` model and throughput weights (5:1).
- [x] Unit and integration test coverage in `tests/test_k8s_llm_gateway.py` with structural tuple equality assertions.
- [x] Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- [x] 100% passing across Gated CI validation suite (`uv run devops ci`).

---

## 2. Verification Results

- `uv run pytest tests/test_k8s_llm_gateway.py`: 26 passed.
- `uv run pytest tests/test_ai_gateway.py tests/test_ai_gateway_tune.py`: 39 passed.
- All manifest invariant assertions verified:
  - `devops-review` vLLM backend weighted at 5 and Ollama-2 weighted at 1 with zero caps.
  - `devops-review` vLLM `max_input_tokens: 61440` < 65536 context length.
  - `devops-review` Ollama-2 `max_input_tokens: 43904` < 48000 context length.
  - `devops-reasoning` `max_input_tokens: 61440` < 65536 context length.
