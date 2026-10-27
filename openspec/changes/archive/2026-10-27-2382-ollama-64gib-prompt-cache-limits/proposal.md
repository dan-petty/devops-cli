# Proposal

## Why

Issue #2382: The `ollama-64gib` pod experienced repeated `OOMKilled` container restarts on node `gemini`.

Node `gemini` has 15.3 GiB of host RAM and two GPUs totaling 64 GiB VRAM. The `ollama-64gib` daemonset runs with `OLLAMA_CONTEXT_LENGTH=160000` and `OLLAMA_KV_CACHE_TYPE=q8_0`. Ollama 0.34.4 delegates inference to `llama-server`. When request processing completes, `llama-server` saves idle slot states into a prompt cache in host RAM. The default cache ceiling is 8,192 MiB (`--cache-ram`, environment variable `LLAMA_ARG_CACHE_RAM`). With 160k context, a single saved prompt can consume over 3.1 GiB. Multiple cached prompts fill host memory beyond the node capacity, which triggers system OOM kills. Furthermore, the `ollama` container sets no memory limit, so the kernel terminates the process.

## What Changes

- Add environment variable `LLAMA_ARG_CACHE_RAM: "4096"` to the `ollama` container in the `ollama-64gib` DaemonSet.
- Set `resources.limits.memory: 12Gi` on the `ollama` container in the `ollama-64gib` DaemonSet.
- Add regression tests in `tests/test_k8s_llm_gateway.py` asserting the prompt cache limit and memory limit on `ollama-64gib`.
- Update `k8s/llm/profiles/ollama-profiles.yaml` comments and `src/devops_cli/ai/knowledge_base/it_domains/tools/ollama.md` to document the cache limit and memory constraints.
- This change alters internal Kubernetes manifests and documentation without modifying public CLI commands or options. The change sets `skip_specs: true` in `.openspec.yaml`.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Manifests: `k8s/llm/profiles/ollama-profiles.yaml`.
- Documentation: `src/devops_cli/ai/knowledge_base/it_domains/tools/ollama.md`.
- Tests: `tests/test_k8s_llm_gateway.py`.

## Feasibility

- Live cluster diagnostics on node `gemini`:
  - `kubectl describe node gemini` confirmed capacity is 16,095,560 KiB (15.3 GiB).
  - Node events recorded: `Warning SystemOOM ... victim process: llama-server`.
  - Pod status showed `OOMKilled` with exit code 137.
- Process inspection of `ollama-64gib-jl47s`:
  - `/bin/ollama serve` executes `/usr/lib/ollama/llama-server` as a child process.
  - `/proc/<pid>/environ` on `llama-server` verified that Ollama passes pod environment variables down to `llama-server`.
  - `/usr/lib/ollama/llama-server --help` confirms `-cram, --cache-ram N` is controlled by environment variable `LLAMA_ARG_CACHE_RAM` (default: 8192 MiB).
  - `/proc/<pid>/status` showed `llama-server` uses ~4.0 GiB base host RAM without prompt cache (CUDA IPC buffers, CPU buffers, mapped files).
  - The pod logs showed prompt save events of 3,172 MiB for 81,367 tokens.
  - Limiting cache to 4,096 MiB caps prompt cache memory while allowing one long prompt cache entry.
  - Setting container memory limit to 12Gi reserves 3.3 GiB on the node for system processes and monitoring daemonsets.
- Audit of other tiers:
  - Inspection of `k8s/llm/profiles/ollama-profiles.yaml` confirmed all 9 tiers currently have unset memory limits on their `ollama` containers.
  - The other serving tiers run with smaller context lengths (48k) or on nodes with 64 GiB host RAM (`condor`, `hog`).

## Existing Tool Considered

`llama-server` provides the native configuration environment variable `LLAMA_ARG_CACHE_RAM` to control host prompt cache sizing. Setting this standard variable and standard Kubernetes container resource limits resolves the issue without introducing custom wrapper scripts or compensating application code.
