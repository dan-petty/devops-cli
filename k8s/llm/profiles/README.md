# Traditional Homelab GPU Inference Profiles & Service Aliases

This directory provides standardized Kubernetes configurations mapping traditional homelab GPU hardware setups to optimal large language models and inference backends (`ollama`, `vllm`).

Every deployed workload carries semantic capability labels (`llm.devops.io/model: <model-alias>`) mapped to stable Kubernetes **Model Service Aliases** (`model-<model-name>`), which front the backend pods and connect into the LLM Gateway (`llm-gateway`) virtual model mesh.

---

## 1. Hardware Matrix & Model Allocation

The matrix systematically maps GPU hardware configurations across counts `[1, 2, 3, 4]`, per-GPU VRAM sizes `[16GiB, 24GiB, 32GiB]`, and inference engines `[ollama, vllm]`:

| GPUs | VRAM / GPU | Total VRAM | Backend | Recommended Model | Model Alias | Service Alias | TP / PP | Max Context | Quantization |
|:---:|:---:|:---:|:---:|:---|:---|:---|:---:|:---:|:---:|
| **1** | 16 GiB | 16 GiB | `ollama` | `qwen2.5-coder:7b` | `qwen2.5-coder-7b` | `model-qwen2-5-coder-7b` | 1 | 32K | Q4_K_M |
| **1** | 16 GiB | 16 GiB | `vllm` | `qwen2.5-coder-14b-instruct` | `qwen2.5-coder-14b` | `model-qwen2-5-coder-14b` | 1 | 16K | AWQ (FP8 KV) |
| **1** | 24 GiB | 24 GiB | `ollama` | `qwen2.5-coder:14b` | `qwen2.5-coder-14b` | `model-qwen2-5-coder-14b` | 1 | 32K | Q8_0 |
| **1** | 24 GiB | 24 GiB | `vllm` | `qwen2.5-coder-14b-instruct` | `qwen2.5-coder-14b` | `model-qwen2-5-coder-14b` | 1 | 32K | AWQ |
| **1** | 32 GiB | 32 GiB | `ollama` | `qwen3-coder:30b` | `qwen3-coder-30b` | `model-qwen3-coder-30b` | 1 | 48K | Q4_K_M |
| **1** | 32 GiB | 32 GiB | `vllm` | `qwen3-coder:30b` | `qwen3-coder-30b` | `model-qwen3-coder-30b` | 1 | 32K | AWQ |
| **2** | 16 GiB | 32 GiB | `ollama` | `qwen3-coder:30b` | `qwen3-coder-30b` | `model-qwen3-coder-30b` | 2 | 32K | Q4_K_M |
| **2** | 16 GiB | 32 GiB | `vllm` | `qwen3-coder:30b` | `qwen3-coder-30b` | `model-qwen3-coder-30b` | 2 | 32K | AWQ |
| **2** | 24 GiB | 48 GiB | `ollama` | `cogito-v2:70b` | `cogito-v2-70b` | `model-cogito-v2-70b` | 2 | 32K | Q4_K_M |
| **2** | 24 GiB | 48 GiB | `vllm` | `qwen3-coder:30b` | `qwen3-coder-30b` | `model-qwen3-coder-30b` | 2 | 64K | AWQ |
| **2** | 32 GiB | 64 GiB | `ollama` | `cogito-v2:70b` | `cogito-v2-70b` | `model-cogito-v2-70b` | 2 | 64K | Q4_K_M |
| **2** | 32 GiB | 64 GiB | `vllm` | `cogito-v2:70b` | `cogito-v2-70b` | `model-cogito-v2-70b` | 2 | 32K | AWQ |
| **3** | 16 GiB | 48 GiB | `ollama` | `cogito-v2:70b` | `cogito-v2-70b` | `model-cogito-v2-70b` | 3 | 32K | Q4_K_M |
| **3** | 16 GiB | 48 GiB | `vllm` | `qwen3-coder:30b` | `qwen3-coder-30b` | `model-qwen3-coder-30b` | 2+1 | 32K | AWQ |
| **3** | 24 GiB | 72 GiB | `ollama` | `cogito-v2:70b` | `cogito-v2-70b` | `model-cogito-v2-70b` | 3 | 64K | Q4_K_M |
| **3** | 24 GiB | 72 GiB | `vllm` | `cogito-v2:70b` | `cogito-v2-70b` | `model-cogito-v2-70b` | PP=3 | 32K | AWQ |
| **3** | 32 GiB | 96 GiB | `ollama` | `cogito-v2:70b` | `cogito-v2-70b` | `model-cogito-v2-70b` | 3 | 128K | Q8_0 |
| **3** | 32 GiB | 96 GiB | `vllm` | `cogito-v2:70b` | `cogito-v2-70b` | `model-cogito-v2-70b` | PP=3 | 64K | AWQ |
| **4** | 16 GiB | 64 GiB | `ollama` | `cogito-v2:70b` | `cogito-v2-70b` | `model-cogito-v2-70b` | 4 | 64K | Q4_K_M |
| **4** | 16 GiB | 64 GiB | `vllm` | `cogito-v2:70b` | `cogito-v2-70b` | `model-cogito-v2-70b` | 4 | 32K | AWQ |
| **4** | 24 GiB | 96 GiB | `ollama` | `cogito-v2:70b` | `cogito-v2-70b` | `model-cogito-v2-70b` | 4 | 128K | Q8_0 |
| **4** | 24 GiB | 96 GiB | `vllm` | `cogito-v2:70b` | `cogito-v2-70b` | `model-cogito-v2-70b` | 4 | 64K | AWQ |
| **4** | 32 GiB | 128 GiB | `ollama` | `cogito-v2:70b` | `cogito-v2-70b` | `model-cogito-v2-70b` | 4 | 128K | Q8_0 |
| **4** | 32 GiB | 128 GiB | `vllm` | `cogito-v2:70b` | `cogito-v2-70b` | `model-cogito-v2-70b` | 4 | 64K | FP8 / BF16 |

---

## 2. Standardized Model Service Aliases

Services defined in [`services.yaml`](file:///workspaces/devops-cli/k8s/llm/profiles/services.yaml) decouple the physical GPU hardware allocation from the consumer routing layer:

1. **`model-qwen2-5-coder-7b`**:
   - Backed by: Any pod labeled with `llm.devops.io/model: qwen2.5-coder-7b`.
   - Ports: `11434` (Ollama), `8000` (vLLM).
   - Serves virtual model: `devops-chat`.
2. **`model-qwen2-5-coder-14b`**:
   - Backed by: Any pod labeled with `llm.devops.io/model: qwen2.5-coder-14b`.
   - Ports: `8000` (vLLM), `11434` (Ollama).
   - Serves virtual model: `devops-coder`.
3. **`model-qwen3-coder-30b`**:
   - Backed by: Any pod labeled with `llm.devops.io/model: qwen3-coder-30b`.
   - Ports: `8000` (vLLM), `11434` (Ollama).
   - Serves virtual model: `devops-reasoning`, `devops-review`.
4. **`model-cogito-v2-70b`**:
   - Backed by: Any pod labeled with `llm.devops.io/model: cogito-v2-70b`.
   - Ports: `8000` (vLLM), `11434` (Ollama).
   - Serves virtual model: `devops-flagship`.
5. **`model-bge-m3`**:
   - Backed by: Any pod labeled with `llm.devops.io/model: bge-m3`.
   - Ports: `11434` (Ollama).
   - Serves virtual model: `devops-embedding`.

---

## 3. Gateway Routing Integration

The LiteLLM AI Gateway (`llm-gateway`) routes incoming API requests using virtual model names to the active service aliases:

```yaml
model_list:
  - model_name: devops-chat
    litellm_params:
      model: ollama_chat/qwen2.5-coder:7b
      api_base: http://model-qwen2-5-coder-7b.llm.svc.cluster.local:11434

  - model_name: devops-coder
    litellm_params:
      model: openai/qwen2.5-coder-14b-instruct
      api_base: http://model-qwen2-5-coder-14b.llm.svc.cluster.local:8000/v1
      api_key: none

  - model_name: devops-reasoning
    litellm_params:
      model: openai/qwen3-coder:30b
      api_base: http://model-qwen3-coder-30b.llm.svc.cluster.local:8000/v1
      api_key: none

  - model_name: devops-review
    litellm_params:
      model: openai/qwen3-coder:30b
      api_base: http://model-qwen3-coder-30b.llm.svc.cluster.local:8000/v1
      api_key: none

  - model_name: devops-flagship
    litellm_params:
      model: openai/cogito-v2:70b
      api_base: http://model-cogito-v2-70b.llm.svc.cluster.local:8000/v1
      api_key: none

  - model_name: devops-embedding
    litellm_params:
      model: ollama/bge-m3
      api_base: http://model-bge-m3.llm.svc.cluster.local:11434
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
