# Traditional Homelab GPU Inference Profiles & Service Architecture

This directory provides standardized Kubernetes configurations mapping traditional homelab GPU hardware setups to optimal large language models and inference backends (`ollama`, `vllm`).

Every deployed workload carries semantic capability labels and is exposed via standardized Kubernetes **Provider-VRAM Services** (`<llm_provider>-<vram_gib>`, e.g., `ollama-16gib`, `vllm-48gib`), which front the backend pods and connect into the LLM Gateway (`llm-gateway`) virtual model mesh.

---

## 1. Hardware Matrix & Model Allocation

The matrix systematically maps GPU hardware configurations across counts `[1, 2, 3, 4]`, per-GPU VRAM sizes `[16GiB, 24GiB, 32GiB]`, and inference engines `[ollama, vllm]`:

| GPUs | VRAM / GPU | Total VRAM | Backend | Recommended Model | Model Alias | Service Alias | TP / PP | Max Context | Quantization |
| :---: | :---: | :---: | :---: | :--- | :--- | :--- | :---: | :---: | :---: |
| **1** | 16 GiB | 16 GiB | `ollama` | `qwen2.5-coder:7b` | `qwen2.5-coder-7b` | `ollama-16gib` | 1 | 32K | Q4_K_M |
| **1** | 16 GiB | 16 GiB | `vllm` | `qwen2.5-coder-14b-instruct` | `qwen2.5-coder-14b` | `vllm-16gib` | 1 | 16K | AWQ (FP8 KV) |
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
| **3** | 16 GiB | 48 GiB | `vllm` | `qwen3-coder:30b` | `qwen3-coder-30b` | `vllm-48gib` | 2+1 | 32K | AWQ |
| **3** | 24 GiB | 72 GiB | `ollama` | `deepseek-r1:70b` | `cogito-v2-70b` | `ollama-72gib` | 3 | 64K | Q4_K_M |
| **3** | 24 GiB | 72 GiB | `vllm` | `deepseek-r1:70b` | `cogito-v2-70b` | `vllm-72gib` | PP=3 | 32K | AWQ |
| **3** | 32 GiB | 96 GiB | `ollama` | `deepseek-r1:70b` | `cogito-v2-70b` | `ollama-96gib` | 3 | 128K | Q8_0 |
| **3** | 32 GiB | 96 GiB | `vllm` | `deepseek-r1:70b` | `cogito-v2-70b` | `vllm-96gib` | PP=3 | 64K | AWQ |
| **4** | 16 GiB | 64 GiB | `ollama` | `deepseek-r1:70b` | `cogito-v2-70b` | `ollama-64gib` | 4 | 64K | Q4_K_M |
| **4** | 16 GiB | 64 GiB | `vllm` | `deepseek-r1:70b` | `cogito-v2-70b` | `vllm-64gib` | 4 | 32K | AWQ |
| **4** | 24 GiB | 96 GiB | `ollama` | `deepseek-r1:70b` | `cogito-v2-70b` | `ollama-96gib` | 4 | 128K | Q8_0 |
| **4** | 24 GiB | 96 GiB | `vllm` | `deepseek-r1:70b` | `cogito-v2-70b` | `vllm-96gib` | 4 | 64K | AWQ |
| **4** | 32 GiB | 128 GiB | `ollama` | `deepseek-r1:70b` | `cogito-v2-70b` | `ollama-128gib` | 4 | 128K | Q8_0 |
| **4** | 32 GiB | 128 GiB | `vllm` | `deepseek-r1:70b` | `cogito-v2-70b` | `vllm-128gib` | 4 | 64K | FP8 / BF16 |

---

## 2. Standardized Provider-VRAM Services (`<llm_provider>-<vram_gib>`)

Services defined in [`services.yaml`](file:///workspaces/devops-cli/k8s/llm/profiles/services.yaml) decouple the physical GPU hardware allocation from the consumer routing layer:

1. **`ollama-16gib`**:
   - Backed by: Any pod labeled with `llm.devops.io/provider: ollama` and `llm.devops.io/vram-gib: 16gib`.
   - Port: `11434` (Ollama).
   - Serves virtual model: `devops-chat`, `devops-embedding`.
2. **`vllm-16gib`**:
   - Backed by: Any pod labeled with `llm.devops.io/provider: vllm` and `llm.devops.io/vram-gib: 16gib`.
   - Port: `8000` (vLLM).
   - Serves virtual model: `devops-coder`.
3. **`ollama-32gib`**:
   - Backed by: Any pod labeled with `llm.devops.io/provider: ollama` and `llm.devops.io/vram-gib: 32gib`.
   - Port: `11434` (Ollama).
   - Serves virtual model: `devops-reasoning`, `devops-review`.
4. **`vllm-48gib`**:
   - Backed by: Any pod labeled with `llm.devops.io/provider: vllm` and `llm.devops.io/vram-gib: 48gib`.
   - Port: `8000` (vLLM).
   - Serves virtual model: `devops-reasoning`, `devops-review`.
5. **`vllm-64gib`**:
   - Backed by: Any pod labeled with `llm.devops.io/provider: vllm` and `llm.devops.io/vram-gib: 64gib`.
   - Port: `8000` (vLLM).
   - Serves virtual model: `devops-flagship`.

---

## 3. Gateway Routing Integration

The LiteLLM AI Gateway (`llm-gateway`) routes incoming API requests using virtual model names to the active `<llm_provider>-<vram_gib>` service endpoints:

```yaml
model_list:
  - model_name: devops-chat
    litellm_params:
      model: ollama_chat/qwen2.5-coder:7b
      api_base: http://ollama-16gib.llm.svc.cluster.local:11434

  - model_name: devops-coder
    litellm_params:
      model: openai/qwen2.5-coder-14b-instruct
      api_base: http://vllm-16gib.llm.svc.cluster.local:8000/v1
      api_key: none

  - model_name: devops-reasoning
    litellm_params:
      model: openai/qwen3-coder:30b
      api_base: http://vllm-48gib.llm.svc.cluster.local:8000/v1
      api_key: none

  - model_name: devops-review
    litellm_params:
      model: openai/qwen3-coder:30b
      api_base: http://vllm-48gib.llm.svc.cluster.local:8000/v1
      api_key: none
      weight: 6
  - model_name: devops-review
    litellm_params:
      model: openai/qwen3-coder:30b
      api_base: http://ollama-32gib.llm.svc.cluster.local:11434/v1
      api_key: none
      weight: 1

  - model_name: devops-flagship
    litellm_params:
      model: openai/deepseek-r1:70b
      api_base: http://vllm-64gib.llm.svc.cluster.local:8000/v1
      api_key: none

  - model_name: devops-embedding
    litellm_params:
      model: ollama/bge-m3
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
