# Knowledge Base: Ollama (Local Large Language Model Inference)

## 1. Overview & Purpose

Ollama is an open-source tool for running large language models (LLMs) locally on developer workstations and servers. In the `devops-cli` ecosystem, Ollama powers local offline AI code reviews (`devops review`), semantic text embedding generation (`nomic-embed-text`), RAG context retrieval, and local model bundling (`devops ai bundle-models`).

---

## 2. Usage Information & Architecture

- **Local Inference Engine**: Exposes standard OpenAI-compatible REST API endpoints at `http://localhost:11434/v1/chat/completions` and `http://localhost:11434/api/embeddings`.
- **GPU Acceleration**: Utilizes CUDA/ROCm when NVIDIA or AMD GPUs are available, falling back automatically to high-performance CPU inference.
- **Model Bundler**: `src/devops_cli/ai/model_bundler.py` provides automated verification and downloading of required models:
  - Default reasoning / chat model: `deepseek-r1:14b` / `llama3.3:70b` / `qwen2.5-coder:14b`.
  - Default embedding model: `nomic-embed-text:latest`.
- **CLI Subcommand**: `devops ai` provides provider configuration, model testing, and RAG indexing.

---

## 3. Common & Advanced Commands

### DevOps CLI AI & Ollama Commands
```bash
# Configure Ollama as the active AI provider with specific model
devops ai config --provider ollama --model qwen2.5-coder:14b

# Bundle and pull required models for local AI workflows
devops ai bundle-models

# Test local LLM inference with a prompt
devops ai chat --prompt "Explain the Kubernetes Pod lifecycle."

# Execute local AI code review on the active repository branch
devops review branch --provider ollama
```

### Standard `ollama` CLI Commands
```bash
# Pull a model from Ollama registry
ollama pull qwen2.5-coder:14b
ollama pull nomic-embed-text

# List installed local models
ollama list

# Inspect model architecture and parameters
ollama show qwen2.5-coder:14b --modelfile

# Run interactive terminal session with a model
ollama run qwen2.5-coder:14b

# Check active running models in VRAM
ollama ps

# Generate an embedding vector via curl
curl http://localhost:11434/api/embeddings -d '{
  "model": "nomic-embed-text",
  "prompt": "DevOps CLI workstation automation"
}'
```

---

## 4. Best Practice Guidance

1. **Model Quantization**: Use `q4_K_M` or `q8_0` quantized models to maximize inference speed while staying within workstation VRAM / RAM limits.
2. **Context Window Sizing**: Set `num_ctx` appropriately (e.g. `8192` or `16384`) in Ollama modelfiles when reviewing large multi-file diffs.
3. **Structured Outputs**: Use JSON schema enforcement or markdown reasoning filters (`ThinkingStreamProcessor`) to extract clean structured data from reasoning models (such as `deepseek-r1`).
4. **Embedding Dimensionality**: Standardize on 768-dimensional embeddings (`nomic-embed-text`) across all local vector storage tables.

---

## 5. Security Recommendations & Zero-Trust Policies

- **100% Offline & Egress-Free**: Ollama executes locally on the workstation; no source code, diffs, or secrets leave the local environment during analysis.
- **Bind Address**: Bind Ollama to `127.0.0.1:11434` (localhost) to prevent unauthorized API calls from external network interfaces.
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
- **DevOps CLI Model Bundler**: [src/devops_cli/ai/model_bundler.py](file:///workspaces/devops-cli/src/devops_cli/ai/model_bundler.py)
