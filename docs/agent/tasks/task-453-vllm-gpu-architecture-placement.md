# Task 453: GPU-Architecture Inference Placement, vLLM Profiles & Authenticated LLM Gateway

**Issue**: [#453](https://github.com/dan-petty/devops-cli/issues/453)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p2-medium`
**Scope**: `type/feature`, `scope/k8s`, `scope/ai`, `priority/p2-medium`

---

## 1. Description & Objectives

The `llm` stack could not run vLLM next to the Ollama DaemonSet. Ollama requests no
`nvidia.com/gpu` and sees every GPU on its node (`NVIDIA_VISIBLE_DEVICES=all`), so the scheduler
never learns that it holds VRAM, while vLLM pre-allocates 95% of each GPU at start. Whichever
engine loaded second failed or spilled to CPU.

The vLLM Deployment itself had four further defects:

- It selected only `nvidia.com/gpu.present`, so it could land on pre-Ampere GPUs vLLM does not
  support, or on GPUs too small for its model.
- It could not download weights: the Squid proxy SSL-bumps HTTPS and vLLM did not trust its CA.
- Weights lived on an `emptyDir` and were re-downloaded on every restart.
- A 60-second liveness delay killed the pod long before a multi-gigabyte first download finished.

### Key Deliverables Completed:

- [x] **Placement by GPU Architecture**: Ampere-or-newer GPUs run vLLM, older architectures run
  Ollama. Every selector accepts both NVIDIA GPU Feature Discovery labels
  (`nvidia.com/gpu.family`) and architecture labels (`nvidia.com/gpu.architecture`); Ollama's
  `NotIn` terms also match nodes carrying neither.
- [x] **Dual-GPU Profile (`k8s/llm/vllm/`)**: 2+ GPUs; Qwen2.5-Coder-32B-Instruct-AWQ at tensor
  parallel 2, 64K context through static YaRN (`--hf-overrides` `rope_parameters`, factor 2 over
  the model's native 32K), `--max-num-seqs 64`. vLLM 0.30 does not multiply YaRN factors into the
  derived length; it expects `max_position_embeddings` to hold the extended 65536 already, so the
  override sets both. Served as `qwen2.5-coder-32b-instruct` for
  `devops-reasoning`.
- [x] **Single-GPU Profile (`k8s/llm/vllm-single/`)**: one GPU with 16 GiB+;
  Qwen2.5-Coder-14B-Instruct-AWQ with an FP8 KV cache and a 16K window. Measured on a 16 GiB
  Blackwell GPU, weights, activations and CUDA graphs leave only 1.39 GiB of KV cache at 0.92
  utilisation, which vLLM sizes at ~15K tokens; 0.95 with FP8 fits one 16K sequence, and longer
  prompts escalate to the dual-GPU profile through the gateway. Memory limit 12 Gi for 16 GiB-RAM workers. Served as `qwen2.5-coder-14b-instruct`
  for `devops-coder`, keeping the 32B → 14B → 7B failover chain within one model family.
- [x] **Deployable Behind the Proxy**: an init container merges the Squid CA into the system
  bundle (`SSL_CERT_FILE`, `REQUESTS_CA_BUNDLE`); `HF_HUB_DISABLE_XET=1`, because Hugging Face Xet
  chunk transfers fail with `401 Unauthorized` from the CAS server through the SSL-bumping proxy; weights persist on a PVC; a 3-hour startup
  probe covers a first download over a slow home link (measured ~1.3 MB/s per stream); `Recreate` rollouts, since a surge pod can never obtain GPUs
  held by the running one. Image pinned to `vllm/vllm-openai:v0.30.0`; `--quantization` is left
  to auto-detection so AWQ uses the Marlin kernels.
- [x] **Authenticated LLM Gateway (`k8s/llm/gateway/`)**: LiteLLM bumped from `v1.61.16` to
  `v1.102.1`; the master key comes from the `llm-gateway-secrets` Secret (created at deploy time,
  never committed) and LiteLLM rejects unauthenticated requests. The Service is a NodePort with a
  Kubernetes-assigned port, the single LAN entry point; its ingress admits any source on 4000
  because the key is the control, while egress stays limited to the inference backends. Router
  timeout raised from 60 s to 600 s for long code reviews on the 32B model.
- [x] **vLLM Behind the Gateway**: both vLLM Services are ClusterIP and their NetworkPolicies admit
  only the gateway, so no unauthenticated path to the GPUs exists. The gateway's egress and
  `NO_PROXY` include `vllm-single`, and the namespace default perimeter excludes it.
- [x] **Context-Window Escalation in the Gateway**: `max_input_tokens` per vLLM model (window minus
  4K reply tokens), `enable_pre_call_checks`, and `context_window_fallbacks` (`devops-chat` →
  `devops-coder` → `devops-reasoning`) route an oversized prompt to a larger model before any
  backend rejects it; an unavailable `devops-coder` falls back to `devops-reasoning` first.
- [x] **Service Links Disabled**: `enableServiceLinks: false`, because the `vllm` Service's injected
  `VLLM_PORT=tcp://...` collides with vLLM's own `VLLM_PORT` setting and aborts worker startup.
- [x] **Open WebUI Through the Gateway**: `values-open-webui.yaml` points the OpenAI connection at
  the gateway with the shared master key (`openaiApiKeyExistingSecret`). Existing installations
  persist connections in their database, which the README documents.
- [x] **Single Source for Served Model Names**: `DEFAULT_VLLM_*` constants in
  `config/defaults.py` drive the gateway and Portkey routes and `scale_vllm`; the LiteLLM and
  Portkey ConfigMaps are asserted against them.
- [x] **Automated Tests & Quality Gates**:
  - `tests/test_k8s_llm_gateway.py`: model arguments, YaRN arithmetic, selectors under both label
    schemes, Ollama's complementary exclusion, CA trust, Xet opt-out, PVCs, probes, gateway image,
    master key, timeout and NodePort, cluster-internal vLLM Services, Open WebUI values, policies
    and kustomization, using structural tuple equality assertions.
  - `tests/test_ai_gateway.py`, `tests/test_ai_gateway_portkey_lightllm.py`: routes, failover to
    the single-GPU profile, `scale_vllm` model identity, Portkey target.
  - Cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

## 2. Verification on a Live Cluster

Deployed to a four-GPU-node k3s cluster (one dual RTX 3090 node, one RTX 5070 Ti node, two
pre-Ampere nodes):

- Placement: `vllm` scheduled only on the dual-GPU Ampere node, `vllm-single` only on the Blackwell
  node, Ollama only on the two pre-Ampere nodes.
- Gateway authentication: `/v1/models` returns 401 without the master key and 200 with it; the
  four virtual models are listed.
- Routing, read from LiteLLM's `x-litellm-model-api-base` response header:
  - `devops-coder`, short prompt → `vllm-single`; `devops-reasoning` → `vllm`.
  - `devops-coder` with a 26,285-token prompt → `vllm` (pre-call context check and fallback).
  - `devops-coder` with `vllm-single` scaled to zero → `vllm` (availability fallback).
- Single-GPU capacity: vLLM reports a 20,288-token KV cache (1.24x concurrency at 16K).
- Open WebUI lists the gateway models through its OpenAI connection.

## 3. Remaining Work (tracked in `docs/ROADMAP.md`)

- `devops ai vllm-scale` (`GatewayRouter.scale_vllm`) models only the dual-GPU profile.
- The bundled GPU Feature Discovery manifest applies no labels without Node Feature Discovery,
  so clusters relying on it need NFD before either vLLM profile can schedule.
