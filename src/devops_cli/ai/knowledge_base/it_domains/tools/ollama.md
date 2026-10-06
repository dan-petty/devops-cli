# Knowledge Base: Ollama (Local Large Language Model Inference)

## 1. Overview & Purpose

Ollama is an open-source tool for running large language models (LLMs) locally on developer workstations and servers. In the `devops-cli` ecosystem, Ollama powers local offline AI code reviews (`devops review`), semantic text embedding generation (`qwen3-embedding:0.6b`), RAG context retrieval, and local model bundling (`devops ai bundle-models`).

---

## 2. Usage Information & Architecture

- **Local Inference Engine**: Exposes standard OpenAI-compatible REST API endpoints at `http://localhost:11434/v1/chat/completions` and `http://localhost:11434/api/embeddings`.
- **GPU Acceleration**: Utilizes CUDA/ROCm when NVIDIA or AMD GPUs are available, falling back automatically to high-performance CPU inference.
- **Model Bundler**: `src/devops_cli/ai/model_bundler.py` provides automated verification and downloading of required models:
  - Default reasoning / review models: `qwen3.8:27b` / `qwen2.5-coder:14b` / `deepseek-r1:14b`.
  - Default embedding model: `qwen3-embedding:0.6b` (768-dimensional vectors).
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

# Route dense vector embedding generation to a dedicated remote host (e.g. http://192.0.2.10:11434)
devops config set ai.allow_private_network true
devops config set ai.tasks.embedding.ollama_urls http://192.0.2.10:11434

# Bundle and pull required models for local AI workflows
devops ai bundle-models

# Test local LLM inference with a prompt
devops ai test --prompt "Explain the Kubernetes Pod lifecycle."

# Execute local AI code review with static scan only (fast 2s pass)
devops ai review path . --static-scan-only

# Execute local AI code review on the active repository branch, on a local model
DEVOPS_CLI_AI_TASK_ANALYSIS_PROVIDER=ollama DEVOPS_CLI_AI_TASK_ANALYSIS_MODEL=qwen3.8:27b devops ai review branch
```

### Standard `ollama` CLI Commands
```bash
# Pull a model from Ollama registry
ollama pull qwen3.8:27b
ollama pull qwen3-embedding:0.6b

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
  "model": "qwen3-embedding:0.6b",
  "prompt": "DevOps CLI workstation automation"
}'
```

---

## 4. Best Practice Guidance & Performance Tuning

1. **Size Concurrency to the KV Cache in Kubernetes / Host Daemons**:
   - Ollama reserves KV cache for `OLLAMA_CONTEXT_LENGTH` × `OLLAMA_NUM_PARALLEL` tokens, so the tiers in [`k8s/llm/profiles/ollama-profiles.yaml`](../../../../../../k8s/llm/profiles/ollama-profiles.yaml) keep one model loaded and serve one request at a time:
     ```yaml
     env:
       - name: OLLAMA_MAX_LOADED_MODELS
         value: "1"
       - name: OLLAMA_NUM_PARALLEL
         value: "1"
     ```
   - `ollama-48gib-slow`, the background tier, keeps two models loaded (`OLLAMA_MAX_LOADED_MODELS: "2"`, `OLLAMA_KEEP_ALIVE: "-1"`): its embedding model and `qwen3.8:27b`, the one generation model the gateway sends it, so neither evicts the other. Ollama also evicts a resident model when it predicts that a new one needs more than 80% of the free VRAM: qwen3.8:27b is predicted to fit beside the embedder, while a dense ~30B model evicted it.
2. **Model Quantization & Sizing**: Use `q4_K_M` or `q8_0` quantized models to maximize inference throughput while staying within workstation VRAM / RAM limits.
3. **Constrain Review Token Generation**: Set `max_tokens: 2048` and `reasoning_effort: low` for code reviews to prevent long generation delays during multi-file reviews.
4. **Context Window Sizing**: Set `num_ctx` appropriately (e.g. `8192` or `16384`) in Ollama modelfiles when reviewing large multi-file diffs.
5. **Structured Outputs & Response Repair**: The review engine automatically normalizes LLM outputs using `repair_json_string` and `ThinkingStreamProcessor` to extract clean JSON schemas.
6. **Embedding Dimensionality**: Standardize on 768-dimensional embeddings (`qwen3-embedding:0.6b`) across all local vector storage tables.

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
