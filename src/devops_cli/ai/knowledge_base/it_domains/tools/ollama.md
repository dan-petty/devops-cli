---
applies_to:
  - "tool:ollama@0.40.*"
sources:
  - "https://ollama.com/"
  - "https://github.com/ollama/ollama"
reviewed: "2026-10-28"
tags:
  - "ollama"
  - "ai"
  - "llm"
---

# Knowledge Base: Ollama (Local Large Language Model Inference)

## 1. Overview & Purpose

Ollama is an open-source tool for running large language models (LLMs) locally on developer workstations and servers. In the `devops-cli` ecosystem, Ollama powers local offline AI code reviews (`devops review`), semantic text embedding generation (`qwen3-embedding:0.6b`), RAG context retrieval, and local model bundling (`devops ai bundle-models`).

---

## 2. Usage Information & Architecture

- **Local Inference Engine**: Exposes standard OpenAI-compatible REST API endpoints at `http://localhost:11434/v1/chat/completions` and `http://localhost:11434/api/embeddings`.
- **GPU Acceleration**: Utilizes CUDA/ROCm when NVIDIA or AMD GPUs are available, falling back automatically to high-performance CPU inference.
- **Model Bundler**: `src/devops_cli/ai/model_bundler.py` provides automated verification and downloading of required models:
  - Default reasoning / review models: `qwen3.8:27b` / `qwen2.5-coder:14b` / `deepseek-r1:14b`.
  - Default embedding model: `qwen3-embedding:0.6b` (1024-dimensional vectors).
- **Concurrency & Parallelism Architecture**:
  - `OLLAMA_NUM_PARALLEL`: Controls the number of concurrent request slots Ollama allocates per model in VRAM (default: 1). Increasing this to `2` or `4` allows parallel file reviews and group analysis.
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

# Show the loaded models, their size, context and expiry (UNTIL) on one cluster tier, such as ollama-48gib
kubectl -n llm exec ds/<tier> -c ollama -- ollama ps

# Generate an embedding vector via curl
curl http://localhost:11434/api/embeddings -d '{
  "model": "qwen3-embedding:0.6b",
  "prompt": "DevOps CLI workstation automation"
}'
```

---

## 4. Best Practice Guidance & Performance Tuning

1. **Size Concurrency to the KV Cache in Kubernetes / Host Daemons**:
   - Ollama reserves KV cache for `OLLAMA_CONTEXT_LENGTH` × `OLLAMA_NUM_PARALLEL` tokens, so the tiers in [`k8s/llm/profiles/ollama-profiles.yaml`](../../../../../../k8s/llm/profiles/ollama-profiles.yaml) serve one request per model at a time. A tier keeps one model loaded:
     ```yaml
     env:
       - name: OLLAMA_MAX_LOADED_MODELS
         value: "1"
       - name: OLLAMA_NUM_PARALLEL
         value: "1"
     ```
   - `ollama-48gib` and `ollama-64gib` load `qwen3.8:27b` and no other model (#3567). They set `OLLAMA_CONTEXT_LENGTH` to 262144 (the native limit, from `ollama show`), `OLLAMA_MAX_LOADED_MODELS: "1"` and `OLLAMA_KEEP_ALIVE: "-1"`, and the gateway sends them no other model and no embedding. With q8_0 KV cache the model takes 27 GB at that length, 100% on the GPUs of `ollama-48gib`. A client that names another model straight to the tier makes Ollama unload `qwen3.8:27b` and load that model.
   - A chat tier that the gateway sends embeddings to keeps two models loaded (`OLLAMA_MAX_LOADED_MODELS: "2"`). No tier does this now: the gateway sends `ollama-16gib` nothing, because its host is unstable. Ollama loads the second model only when both fit in VRAM, and otherwise unloads the idle one, so `qwen3-embedding:0.6b` stays beside the chat model where it fits. The gateway sends `num_ctx: 8192` with each embedding, so the embedder needs 2.2 to 2.9 GB, not the 3.1 to 5.2 GB of its 32,768-token default.
   - `ollama-24gib-embed-gpu0` and `-gpu1` serve the embedding model alone, one instance on each GPU of a Pascal node, and keep it loaded for good (`OLLAMA_KEEP_ALIVE: "-1"`). `k8s/llm/profiles/gpu-thresholds.yaml` sets which tiers do this (#3501).
   - Measured on Ollama 0.40.12 on two Quadro P6000, with source code in chunks of about 300 tokens, in batches of 32 (#3501, #3518):
     - Time is proportional to tokens: about 5 ms for each input and 0.16 ms for each token, or about 6,000 tokens a second. A batch of 1 and a batch of 64 have the same time for each input, so batch size does not change throughput on this GPU.
     - One instance gives 0.56 batches a second, and two give 1.10. `OLLAMA_NUM_PARALLEL` of 1, 2 and 4 and `num_batch` of 1024, 2048 and 8192 give no gain. Add GPUs for throughput.
     - `LLAMA_ARG_THREADS: "1"` gives the same speed and exactly equal vectors with 1.2 CPU cores, not 12: the default threads only spin when the model runs on the GPU. The `num_thread` request option does the same, but a caller that sends another value reloads the model (4.3 s).
     - Through the gateway, `simple-shuffle` gives 0.85 to 1.08 batches a second, because two batches can land on one GPU. `least-busy` sends every embedding batch to the first deployment, and gives 0.55.
     - Vectors are exactly equal for a repeat and across the two GPUs, and cosine 1.0 across batch size and input order. An input longer than `num_ctx` is cut with no error: 44,000 characters gave 8,191 tokens and status 200.
     - Under sustained load, one GPU reached 87 °C, above its 83 °C target, and its clock held at 1,506 MHz against a maximum of 1,657 MHz. Its slowdown temperature is 97 °C.
   - Ollama also evicts a resident model when it predicts that a new one needs more than 80% of the free VRAM.
   - The gateway sends no `keep_alive`, and a call without `keep_alive` keeps the keep-alive of the loaded model:
     - A call through the gateway keeps the lease that `devops ai prewarm` set (one hour by default). Ollama starts that lease again when the call ends.
     - A model that a gateway call loads gets the default keep-alive of its tier: `OLLAMA_KEEP_ALIVE`, or 5 minutes when the tier does not set it.
     - A request that sends `keep_alive` replaces the lease. Thus a prewarm with `keep_alive: 1h` replaces the forever lease of `ollama-24gib-embed-gpu0`, `ollama-48gib` or `ollama-64gib` with one hour. The next call through the gateway loads the model again with the forever lease of the tier. This comes from `useLoadedRunner` in the source, and nobody tested it on a live tier.
     - Source: in Ollama 0.40.12 `server/sched.go`, `useLoadedRunner` changes the lease only when a request sends `keep_alive`. `load` uses `OLLAMA_KEEP_ALIVE` only when a request that loads a model sends none.
     - Test: on 2026-10-24, on an idle tier, a prewarm with `keep_alive: 1h` set the expiry one hour later. Then `/api/chat` (blocking and streamed) and `/api/embed` without `keep_alive` kept the one-hour expiry.
   - **Prompt Cache RAM Limits in llama-server**:
     - Ollama runs `llama-server` as a child process. By default, `llama-server` reserves up to 8,192 MiB in host RAM for prompt caching across idle slots.
     - To bound host RAM consumption on nodes with high context windows, set environment variable `LLAMA_ARG_CACHE_RAM`.
     - The `ollama-64gib` tier sets `LLAMA_ARG_CACHE_RAM: "4096"` and `limits.memory: 12Gi` to prevent host memory exhaustion on 16 GiB nodes (#2382). Node `gemini` now has 62.5 GiB, and the bounds stay.
     - The `ollama-16gib` tier sets `limits.memory: 8Gi`, equal to its request, and no cache bound (#5115). Its node has 16 GiB, and the tier serves nothing, so a long session past the gateway ends in an OOM kill of the container, not of the node.
2. **Model Quantization & Sizing**: Use `q4_K_M` or `q8_0` quantized models to maximize inference throughput while staying within workstation VRAM / RAM limits.
3. **Constrain Review Token Generation**: Set `max_tokens: 2048` and `reasoning_effort: low` for code reviews to prevent long generation delays during multi-file reviews.
4. **Context Window Sizing**: Set `num_ctx` appropriately (e.g. `8192` or `16384`) in Ollama modelfiles when reviewing large multi-file diffs.
5. **Structured Outputs & Response Repair**: The review engine automatically normalizes LLM outputs using `repair_json_string` and `ThinkingStreamProcessor` to extract clean JSON schemas.
6. **Embedding Dimensionality**: Standardize on 1024-dimensional embeddings (`qwen3-embedding:0.6b`) across all local vector storage tables.

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
