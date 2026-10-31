# Proposal

## Why

Issue #2822: tier `ollama-48gib` (node condor, 2 RTX 3090) runs at a context length of 128000, and tier `ollama-16gib` (node hawk, RTX 5070 Ti) at 48000. The models of both tiers accept more, and the GPUs hold more. The owner wants the longer context where the hardware allows it.

## What Changes

- `OLLAMA_CONTEXT_LENGTH` of `ollama-48gib` goes from 128000 to 262144, the native limit of `qwen3-coder:30b` and `qwen3.8:27b`.
- `OLLAMA_CONTEXT_LENGTH` of `ollama-16gib` goes from 48000 to 131072, the native limit of `gpt-oss:20b`.
- The gateway `max_input_tokens` of the three routes to `ollama-48gib` follow, rendered with `devops ai gateway render --apply`.
- The header of `ollama-profiles.yaml` records the measured numbers and why the other tiers stay.
- The change sets `skip_specs: true` in `.openspec.yaml`: it changes two manifest values and the values that follow from them. No command, option or message changes.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Cluster: the DaemonSets `ollama-48gib` and `ollama-16gib` restart when Argo CD syncs. A loaded model reloads at its new length.
- Gateway: `k8s/llm/gateway/config.yaml`.

## Feasibility

Measured on 2026-10-31 in the running pods, with a temporary model made from the real one with a larger `num_ctx` (removed after the test):

- `qwen3-coder:30b` on condor at 128000: `ollama ps` shows 30 GB, and the GPUs hold 15.3 and 14.5 GiB.
- The same model at 262144: 37 GB, 100% GPU, with 18.9 and 17.9 GiB used of 24 GiB. About 6 GiB per GPU stays free. The 7-day peak of the node was 32.8 of 48 GiB, and the host uses 29% of 64 GB of memory.
- A prompt of 142214 tokens was read in 84 s (1690 tokens/s) and the model answered the instruction at its end. GPU memory did not grow.
- `gpt-oss:20b` on hawk at 131072 with q4_0 KV cache: 13 GB, with 13.7 of 16.3 GiB used on the GPU.
- Arithmetic from `ollama show -v`: KV cache per token with q8_0 is 51 KiB for `qwen3-coder:30b`, 34 KiB for `qwen3.8:27b` (only every fourth layer keeps a cache) and 170 KiB for the 70B models. That is why `ollama-64gib` stays: its 70B models fill the tier at 160000.

## Existing Tool Considered

Ollama's own `OLLAMA_CONTEXT_LENGTH` and the existing `devops ai gateway render`. Nothing is built.
