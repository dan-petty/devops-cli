# Traditional Homelab GPU Inference Profiles & Service Architecture

This directory provides standardized Kubernetes configurations mapping traditional homelab GPU hardware setups to optimal large language models; the deployed backend is `ollama` (vLLM rows remain only in the `devops k8s gpu-matrix` catalogue).

Every deployed workload carries semantic capability labels and is exposed via standardized Kubernetes **Provider-VRAM Services** (`<llm_provider>-<vram_gib>`, e.g., `ollama-16gib`, `ollama-48gib`), which front the backend pods and connect into the LLM Gateway (`llm-gateway`) virtual model mesh.

---

## 1. Hardware Matrix & Model Allocation

The matrix systematically maps GPU hardware configurations across counts `[1, 2, 3, 4]`, per-GPU VRAM sizes `[16GiB, 24GiB, 32GiB]`, and inference engines `[ollama, vllm]`:

| GPUs | VRAM / GPU | Total VRAM | Backend | Recommended Model | Model Alias | Service Alias | TP / PP | Max Context | Quantization |
| :---: | :---: | :---: | :---: | :--- | :--- | :--- | :---: | :---: | :---: |
| **1** | 16 GiB | 16 GiB | `ollama` | `qwen2.5-coder:7b` | `qwen2.5-coder-7b` | `ollama-16gib` | 1 | 32K | Q4_K_M |
| **1** | 16 GiB | 16 GiB | `vllm` | `qwen2.5-coder-14b-instruct` | `qwen2.5-coder-14b` | `vllm-16gib` | 1 | 16K | AWQ |
| **1** | 24 GiB | 24 GiB | `ollama` | `qwen2.5-coder:14b` | `qwen2.5-coder-14b` | `ollama-24gib` | 1 | 32K | Q8_0 |
| **1** | 24 GiB | 24 GiB | `vllm` | `qwen2.5-coder-14b-instruct` | `qwen2.5-coder-14b` | `vllm-24gib` | 1 | 32K | AWQ |
| **1** | 32 GiB | 32 GiB | `ollama` | `qwen3-coder:30b` | `qwen3-coder-30b` | `ollama-32gib` | 1 | 48K | Q4_K_M |
| **1** | 32 GiB | 32 GiB | `vllm` | `qwen3-coder:30b` | `qwen3-coder-30b` | `vllm-32gib` | 1 | 32K | AWQ |
| **2** | 16 GiB | 32 GiB | `ollama` | `qwen3-coder:30b` | `qwen3-coder-30b` | `ollama-32gib` | 2 | 32K | Q4_K_M |
| **2** | 16 GiB | 32 GiB | `vllm` | `qwen3-coder:30b` | `qwen3-coder-30b` | `vllm-32gib` | 2 | 32K | AWQ |
| **2** | 24 GiB | 48 GiB | `ollama` | `deepseek-r1:70b` | `cogito-v2-70b` | `ollama-48gib` | 2 | 32K | Q4_K_M |
| **2** | 24 GiB | 48 GiB | `vllm` | `qwen3-coder:30b` | `qwen3-coder-30b` | `vllm-48gib` | 2 | 64K | AWQ |
| **2** | 32 GiB | 64 GiB | `ollama` | `deepseek-r1:70b` | `cogito-v2-70b` | `ollama-64gib` | 2 | 64K | Q4_K_M |
| **2** | 32 GiB | 64 GiB | `vllm` | `deepseek-r1:70b` | `cogito-v2-70b` | `vllm-64gib` | 2 | 32K | AWQ |
| **3** | 16 GiB | 48 GiB | `ollama` | `deepseek-r1:70b` | `cogito-v2-70b` | `ollama-48gib` | 3 | 32K | Q4_K_M |
| **3** | 16 GiB | 48 GiB | `vllm` | `qwen3-coder:30b` | `qwen3-coder-30b` | `vllm-48gib` | 2 | 32K | AWQ |
| **3** | 24 GiB | 72 GiB | `ollama` | `deepseek-r1:70b` | `cogito-v2-70b` | `ollama-72gib` | 3 | 64K | Q4_K_M |
| **3** | 24 GiB | 72 GiB | `vllm` | `deepseek-r1:70b` | `cogito-v2-70b` | `vllm-72gib` | 2 | 32K | AWQ |
| **3** | 32 GiB | 96 GiB | `ollama` | `deepseek-r1:70b` | `cogito-v2-70b` | `ollama-96gib` | 3 | 128K | Q8_0 |
| **3** | 32 GiB | 96 GiB | `vllm` | `deepseek-r1:70b` | `cogito-v2-70b` | `vllm-96gib` | 2 | 64K | AWQ |
| **4** | 16 GiB | 64 GiB | `ollama` | `deepseek-r1:70b` | `cogito-v2-70b` | `ollama-64gib` | 4 | 64K | Q4_K_M |
| **4** | 16 GiB | 64 GiB | `vllm` | `deepseek-r1:70b` | `cogito-v2-70b` | `vllm-64gib` | 4 | 32K | AWQ |
| **4** | 24 GiB | 96 GiB | `ollama` | `deepseek-r1:70b` | `cogito-v2-70b` | `ollama-96gib` | 4 | 128K | Q8_0 |
| **4** | 24 GiB | 96 GiB | `vllm` | `deepseek-r1:70b` | `cogito-v2-70b` | `vllm-96gib` | 4 | 64K | AWQ |
| **4** | 32 GiB | 128 GiB | `ollama` | `deepseek-r1:70b` | `cogito-v2-70b` | `ollama-128gib` | 4 | 128K | Q8_0 |
| **4** | 32 GiB | 128 GiB | `vllm` | `deepseek-r1:70b` | `cogito-v2-70b` | `vllm-128gib` | 4 | 64K | FP8 |

---

## 2. Standardized Provider-VRAM Services (`<llm_provider>-<vram_gib>`)

Services defined in [`services.yaml`](services.yaml): one ClusterIP Service per Ollama tier (`ollama-16gib`, `ollama-24gib`, `ollama-32gib`, `ollama-48gib`, `ollama-64gib`, `ollama-72gib`, `ollama-96gib`, `ollama-128gib`), each selecting pods labelled `llm.devops.io/provider: ollama` and `llm.devops.io/vram-gib: <n>gib` on port 11434; the gateway's model-to-tier mapping lives in `../gateway/configmap.yaml`.

---

## 3. Gateway Routing Integration

The LiteLLM AI Gateway (`llm-gateway`) routes incoming API requests using virtual model names to the active `<llm_provider>-<vram_gib>` service endpoints. Excerpt from `k8s/llm/gateway/configmap.yaml`:

```yaml
model_list:
  - model_name: devops-chat
    litellm_params:
      model: ollama_chat/hf.co/ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF:IQ3_S
      api_base: http://ollama-16gib-fast.llm.svc.cluster.local:11434
      model_info:
        max_input_tokens: 96000
      weight: 10
  - model_name: devops-chat
    litellm_params:
      model: ollama_chat/qwen3.8:27b
      api_base: http://ollama-48gib-fast.llm.svc.cluster.local:11434
      model_info:
        max_input_tokens: 128000
      weight: 5

  - model_name: devops-coder
    litellm_params:
      model: ollama_chat/qwen3-coder:30b
      api_base: http://ollama-48gib-fast.llm.svc.cluster.local:11434

  - model_name: devops-reasoning
    litellm_params:
      model: ollama_chat/qwen3-coder:30b
      api_base: http://ollama-48gib-fast.llm.svc.cluster.local:11434

  - model_name: bge-m3:latest
    litellm_params:
      model: ollama/bge-m3:latest
      api_base: http://ollama-48gib-slow.llm.svc.cluster.local:11434
      weight: 3
    model_info:
      mode: embedding

  - model_name: devops-review
    litellm_params:
      model: ollama_chat/qwen3-coder:30b
      api_base: http://ollama-48gib-fast.llm.svc.cluster.local:11434
      weight: 9
      num_retries: 0
  - model_name: devops-review
    litellm_params:
      model: ollama_chat/gpt-oss:20b
      api_base: http://ollama-16gib-fast.llm.svc.cluster.local:11434
      weight: 6
      num_retries: 0

  - model_name: embeddinggemma:300m
    litellm_params:
      model: ollama/embeddinggemma:300m
      api_base: http://ollama-16gib.llm.svc.cluster.local:11434
```

---

## 4. Inspection & Matrix Queries

Use the `devops k8s gpu-matrix` CLI command to inspect profiles:

```bash
# Display the full matrix in a rich terminal table
devops k8s gpu-matrix

# Query optimal profile for a 2x 24GB vLLM node
devops k8s gpu-matrix --gpus 2 --vram 24 --backend vllm

# Output machine-readable JSON or YAML
devops k8s gpu-matrix --format json
```
