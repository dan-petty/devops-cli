# Proposal

## Why

Issue #2368: the gateway deployment `hf.co/ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF:IQ3_S` on `ollama-16gib-fast` returns HTTP 500 on approximately 300 calls a day. Diagnostics show that Qwen3.8 chat templates reject requests lacking a user query with `Jinja Exception: No user query found in messages.`. In addition, Ollama requires 20.7 GiB of VRAM for the 48000 context length on this model. The physical 16 GiB GPU offloads most layers to CPU memory. This offload causes severe latency and client timeouts.

## What Changes

- Remove the `hf.co/ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF:IQ3_S` deployment on `ollama-16gib-fast` from `qwen3.8:27b` and `devops-chat` in `k8s/llm/gateway/config.yaml`.
- Update `k8s/llm/profiles/README.md` to reflect the removal of the deployment.
- Update `tests/test_k8s_llm_gateway.py` to assert that `qwen3.8:27b` and `devops-chat` route only to tiers with at least 48 GiB of VRAM.
- Add an OpenSpec delta in `specs/ai-gateway-routing/spec.md`.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-gateway-routing`: ADDED requirement that the gateway routes `qwen3.8:27b` and `devops-chat` only to 48gib and 64gib tiers.

## Impact

- Manifests: `k8s/llm/gateway/config.yaml`.
- Documentation: `k8s/llm/profiles/README.md`.
- Tests: `tests/test_k8s_llm_gateway.py`.

## Feasibility

- Live pod log inspection on `ollama-16gib-tpqj8` identified the exact Ollama error text: `msg="chat template prompt error" error="template: :7: executing \"\" at <$tool_call_start>: Jinja Exception: No user query found in messages."`.
- Live probe confirmed that chat requests with only system or tool messages cause HTTP 500 on `IQ3_S`.
- Ollama memory prediction logs show `predicted="20.7 GiB"` and `available="13.3 GiB"` on `ollama-16gib-tpqj8`. This forces 53 to 56 of 64 model layers onto CPU memory.
- Prometheus query logs confirm the bursts do not agree with embedding calls. The pod served only 3 embedding calls in 24 hours, whereas HTTP 500 bursts occurred throughout the day during agent sessions.
- The proper fix is the removal of the deployment from `qwen3.8:27b` and `devops-chat`. Neither `max_input_tokens` nor tier profiles resolve the chat template crash and the physical VRAM limit.

## Existing Tool Considered

LiteLLM routes all gateway traffic. We update the declarative LiteLLM configuration in `k8s/llm/gateway/config.yaml`. We write no new routing code or custom error filters.
