# Knowledge Base Task: RAG Semantic Context Indexing & Knowledge Retrieval

## 1. Overview & Purpose

Retrieval-Augmented Generation (RAG) in `devops-cli` indexes codebase documentation, architecture decisions, CLI commands, and operational procedures into a local vector database. A natural language query retrieves the chunks most similar to its text and injects them into the prompt context. A code review asks the index in two places: each page's persona prompt gets up to three chunks retrieved with the page's file path and symbol names, not with what a finding names, and the verifier gets up to two chunks per finding, retrieved with the finding's title and description. Both are marked as untrusted context. A review writes nothing to the index, so it gets only what `devops ai rag index` and `index-kb` put there, and nothing when the index is empty or RAG is off.

---

## 2. Architecture & RAG Pipeline

```mermaid
graph TD
    A[Markdown Docs & Python Source] --> B[Text Chunking & Token Sizing]
    B --> C[Vector Embedding qwen3-embedding:0.6b / Ollama]
    C --> D[Vector Index (Qdrant)]
    D --> E[Semantic Similarity Query cosine distance]
    E --> F[Top-K Context Chunks]
    F --> G[Query & Chat Prompt]
    F --> H[Review Page & Verifier Prompts: untrusted context]
```

- **Vector Storage**: Connects to a Qdrant server by URL (`qdrant.url`, or the in-cluster `llm/qdrant` service via the Kubernetes API proxy); no embedded mode is used; `.data/rag/` holds only the local index cache.
- **Embeddings**: Utilizes local Ollama (`qwen3-embedding:0.6b`; override via the rag embedding task model) or external providers to generate normalized vectors.
- **Query Ranking**: Computes cosine similarity scores to rank and extract the most relevant top-K documentation chunks.

---

## 3. Useful Usage Information & Common Commands

### RAG Commands
```bash
# Index workspace documentation and architecture guides into local vector store
devops ai rag index docs/

# Query indexed knowledge base with natural language
devops ai rag query "How do I deploy the Prometheus and Grafana stack?"

# Inspect RAG database stats and indexed document count
devops ai rag status

# Clear the RAG index (re-run `devops ai rag index` to rebuild)
devops ai rag clear
```

---

## 4. Best Practice Guidance

1. **Optimal Chunk Sizing**: Use sliding window chunking (1000–1500 tokens with 100 token overlap) to preserve semantic coherence across headings and code blocks.
2. **Include Structural Metadata**: Attach file path, heading hierarchy, and source repository names as metadata attributes on each indexed chunk.
3. **Re-index After Documentation Updates**: Re-run `devops ai rag index` whenever major documentation or architectural changes are merged.
4. **Grounded Inferences**: Instruct LLM prompts to cite specific document paths when answering queries based on retrieved context.
5. **Serve the Embedding Model, or Turn RAG Off**: Embeddings come from the model configured under `ai.tasks.embedding`, or not at all. A failed request raises `EmbeddingsError`, naming the model, the endpoint or Ollama nodes, and the HTTP status or error. No stand-in vector is made. In a review, chat or analysis run, an error from an unknown or unserved embedding model turns RAG off for the rest of the run and logs one warning that says how to fix it. Transient errors (timeouts, connection resets, rate limits, 5xx) skip that lookup, and after three consecutive transient failures a circuit breaker pauses RAG lookups for 60 seconds; afterwards, a single lookup probes to resume lookups once healthy. Lookups that arrive concurrently while no lookup has succeeded wait for the probe's outcome, running concurrently on success and skipping on failure. Later lookups during a pause send no request, so a node that keeps one model loaded does not swap out the review model for the embedding model. `devops ai rag index`, `index-kb`, `query` and `drift --auto-sync`, and `devops ai ingest index-libraries` and `query-library`, exit 1 with the error, and indexing stores no vector for a text the model did not embed. To fix it, serve the model on a backend, point `ai.tasks.embedding` at a backend that serves it, or set `ai.rag.enabled: false`.

---

## 5. Security Recommendations & Zero-Trust Policies

- **100% Local Vectors**: Vector embeddings and similarity lookups run locally without sending source content to third-party embedding APIs when using Ollama.
- **Filter Sensitive Files**: Exclude `.env`, `.pem`, `id_rsa`, `.key`, and secret files from the indexing scanner pipeline.

---

## 6. General Standards & Reference Guidelines

- **Index Cache Path**: `.data/rag/`.
- **Default Embedding Model**: `qwen3-embedding:0.6b` (Ollama).

---

## 7. Official References & Published Artifacts

- **Ollama Embedding Model**: [ollama.com/library/qwen3-embedding](https://ollama.com/library/qwen3-embedding)
- **DevOps CLI RAG Subsystem**: [src/devops_cli/ai/rag/](../../../../ai/rag/)
- **RAG Command Module**: [src/devops_cli/commands/ai.py](../../../../commands/ai.py)
