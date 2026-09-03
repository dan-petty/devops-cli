# Knowledge Base: Ollama (Local Large Language Model Inference)

## 1. Overview & Purpose

Ollama is an open-source tool for running large language models (LLMs) locally on developer workstations and servers. In the `devops-cli` ecosystem, Ollama powers local offline AI code reviews (`devops review`), semantic text embedding generation (`nomic-embed-text`), RAG context retrieval, and local model bundling (`devops ai bundle-models`).

---

## 2. Usage Information & Architecture

- **Local Inference Engine**: Exposes standard OpenAI-compatible REST API endpoints at `http://localhost:11434/v1/chat/completions` and `http://localhost:11434/api/embeddings`.
- **GPU Acceleration**: Utilizes CUDA/ROCm when NVIDIA or AMD GPUs are available, falling back automatically to high-performance CPU inference.
- **Model Bundler**: `src/devops_cli/ai/model_bundler.py` provides automated verification and downloading of required models:
  - Default reasoning / review models: `qwen3.8:27b` / `qwen2.5-coder:14b` / `deepseek-r1:14b`.
  - Default embedding model: `nomic-embed-text:latest` (768-dimensional vectors).
- **Concurrency & Parallelism Architecture**:
  - `OLLAMA_NUM_PARALLEL`: Controls the number of concurrent request slots Ollama allocates per model in VRAM (default: 1). Increasing this to `2` or `4` allows parallel multi-persona file reviews.
  - `OLLAMA_KV_CACHE_TYPE`: Sets KV cache precision (`f16`, `q8_0`, `q4_0`). Setting `OLLAMA_KV_CACHE_TYPE=q4_0` reduces per-slot VRAM consumption by ~50%, enabling higher parallel request slots without out-of-memory errors.
  - `OLLAMA_MAX_LOADED_MODELS`: Maximum number of models kept concurrent in GPU memory (e.g. running LLM and embedding model concurrently).
- **Reasoning Models & Token Budgeting**:
  - For reasoning models (`qwen3.8:27b`, `deepseek-r1`), the CLI supports `reasoning_effort: low | medium | high`.
  - The response pipeline parses thought streams (`<think>...</think>`) and enforces token limits (`max_tokens`) to ensure fast, concise findings.

---

## 3. Common & Advanced Commands

### DevOps CLI AI & Ollama Commands
```bash
# Configure Ollama as the active AI provider with specific model and reasoning effort
devops config set ai.provider ollama
devops config set ai.model qwen3.8:27b
devops config set ai.reasoning_effort low

# Route dense vector embedding generation to a dedicated remote/homelab host (e.g. workhorse.lan)
devops config set ai.allow_private_network true
devops config set ai.rag.embedding_url http://workhorse.lan:11434
# OR via per-task override:
devops config set ai.tasks.embedding.ollama_urls http://workhorse.lan:11434

# Bundle and pull required models for local AI workflows
devops ai bundle-models

# Test local LLM inference with a prompt
devops ai chat --prompt "Explain the Kubernetes Pod lifecycle."

# Execute local AI code review with static scan only (fast 2s pass)
devops ai review path . --static-scan-only

# Execute local AI code review on the active repository branch
devops ai review branch --provider ollama --model qwen3.8:27b
```

### Standard `ollama` CLI Commands
```bash
# Pull a model from Ollama registry
ollama pull qwen3.8:27b
ollama pull nomic-embed-text

# List installed local models
ollama list

# Inspect model architecture and parameters
ollama show qwen3.8:27b --modelfile

# Run interactive terminal session with a model
ollama run qwen3.8:27b

# Check active running models in VRAM
ollama ps

# Generate an embedding vector via curl
curl http://localhost:11434/api/embeddings -d '{
  "model": "nomic-embed-text",
  "prompt": "DevOps CLI workstation automation"
}'
```

---

## 4. Best Practice Guidance & Performance Tuning

1. **Optimize Concurrency in Kubernetes / Host Daemons**:
   - When deploying Ollama via Kubernetes ([`k8s/llm/ollama-daemonset.yaml`](../../../../../../k8s/llm/ollama-daemonset.yaml)), configure:
     ```yaml
     env:
       - name: OLLAMA_NUM_PARALLEL
         value: "2"
       - name: OLLAMA_KV_CACHE_TYPE
         value: "q4_0"
     ```
2. **Model Quantization & Sizing**: Use `q4_K_M` or `q8_0` quantized models to maximize inference throughput while staying within workstation VRAM / RAM limits.
3. **Constrain Review Token Generation**: Set `max_tokens: 2048` and `reasoning_effort: low` for code reviews to prevent long generation delays during multi-file reviews.
4. **Context Window Sizing**: Set `num_ctx` appropriately (e.g. `8192` or `16384`) in Ollama modelfiles when reviewing large multi-file diffs.
5. **Structured Outputs & Response Repair**: The review engine automatically normalizes LLM outputs using `repair_json_string` and `ThinkingStreamProcessor` to extract clean JSON schemas.
6. **Embedding Dimensionality**: Standardize on 768-dimensional embeddings (`nomic-embed-text`) across all local vector storage tables.

---

## 5. Security Recommendations & Zero-Trust Policies

- **100% Offline & Egress-Free**: Ollama executes locally on the workstation or local cluster node; no source code, diffs, or secrets leave the local environment during analysis.
- **Bind Address & NetworkPolicy**: Bind Ollama to `127.0.0.1:11434` on workstations, or isolate cluster daemonsets with Kubernetes `NetworkPolicy` to only accept traffic from within the cluster.
- **Prompt Sanitization**: Ensure prompt boundary tags (`<untrusted_diff>`) are sanitized to protect against prompt injection attacks.

---

## 6. General Standards & Reference Guidelines

- **Default Port**: Standard Ollama HTTP port `11434`.
- **Modelfile Declarations**: Store custom model definitions under `src/devops_cli/ai/models/` or dedicated Modelfile manifests.

---

## 7. Official References & Published Artifacts

- **Project Homepage**: [ollama.com](https://ollama.com/)
- **Public Git Repository**: [github.com/ollama/ollama](https://github.com/ollama/ollama)
- **Official Model Library**: [ollama.com/library](https://ollama.com/library)
- **DevOps CLI Model Bundler**: [src/devops_cli/ai/model_bundler.py](../../../model_bundler.py)
