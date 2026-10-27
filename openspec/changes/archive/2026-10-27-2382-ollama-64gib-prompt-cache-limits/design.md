# Design

## Overview

The `ollama-64gib` DaemonSet serves inference using `qwen3.8:27b` and `gemma4:31b` with a context window of 160,000 tokens on node `gemini`. Node `gemini` has 15.3 GiB of physical host RAM. Ollama uses `llama-server` as its backend runner. When `llama-server` processes requests, it stores idle slot KV states in a host RAM prompt cache.

To prevent node memory exhaustion and container termination, we bound the host RAM cache and specify a container memory limit:
1. Set `LLAMA_ARG_CACHE_RAM: "4096"` in the container environment.
2. Set `resources.limits.memory: 12Gi` on the container.

## Architecture and Sizing Calculations

### Node Memory Budget on `gemini`

- Total physical memory: 15.35 GiB (15,718 MiB).
- System overhead (k3s, containerd, kubelet, Linux kernel): ~1.50 GiB.
- Monitoring and helper daemonsets (`alloy-logs`, `alloy-profiles`, `dcgm-exporter`, `node-exporter`, `gpu-feature-discovery`): ~1.10 GiB active usage (requests ~1.0 GiB, limits ~2.8 GiB).
- Available memory headroom for the `ollama` workload: ~12.75 GiB.

### Container Memory Budget

- `llama-server` base memory without prompt cache: ~4.0 GiB (CUDA IPC shared memory, CPU scratch buffers, mapped model files, and draft model).
- Ollama Go server daemon: ~0.3 GiB.
- `LLAMA_ARG_CACHE_RAM`: bounded to 4,096 MiB (~4.0 GiB). This permits caching one large prompt (e.g. 81k tokens = 3.17 GiB).
- Expected peak container memory: ~4.3 GiB + 4.0 GiB = ~8.3 GiB.
- Peak with secondary embedding model loaded concurrently (`OLLAMA_MAX_LOADED_MODELS=2`): ~10.0 GiB.
- Container limit `12Gi` (12,288 MiB) provides safety margin while strictly protecting the 15.3 GiB host from kernel OOM invocations.

## Rejected Alternatives

### 1. Completely Disabling Prompt Cache (`LLAMA_ARG_CACHE_RAM: "0"`)

- **Rejected**: Completely disabling the prompt cache eliminates prompt KV caching across slot releases. For multi-turn chats or agent workflows, every request must recompute the entire prompt prefix from scratch. That increases inference latency and GPU processing load unnecessarily.
- **Evidence**: Setting `LLAMA_ARG_CACHE_RAM: "4096"` provides sufficient protection while preserving prompt reuse.

### 2. Setting `LLAMA_ARG_CACHE_RAM: "2048"`

- **Rejected**: A prompt of 81,367 tokens takes 3,172.8 MiB. A 2,048 MiB cache limit cannot hold a single long prompt on this tier.
- **Evidence**: Pod logs showed saved prompt size was 3,172.830 MiB. A 2,048 MiB cache would drop long prompt saves entirely.

### 3. Setting Memory Limits on All 9 Tiers

- **Rejected**: The issue specifically targets `ollama-64gib` which runs on node `gemini` with a high context-to-RAM ratio (160k context on 15.3 GiB RAM). Other tiers either run small context sizes (48k) or schedule on nodes with 64 GiB RAM (`condor`, `hog`). In addition, `tests/test_k8s.py` explicitly tests unconstrained memory limits on the default tier (`ollama-16gib`) for node-adaptive scaling.
- **Evidence**: Changing all tiers would violate existing test contracts and unnecessarily constrain tiers deployed on high-memory hardware.
