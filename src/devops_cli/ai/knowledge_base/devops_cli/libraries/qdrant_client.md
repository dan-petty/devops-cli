# Code Library: Qdrant Client (Vector Embeddings & Semantic Search)

## 1. Project References

| Resource | Endpoint / URL |
| :--- | :--- |
| **Official Documentation** | [qdrant.tech/documentation](https://qdrant.tech/documentation/) |
| **Public Git Repository** | [github.com/qdrant/qdrant-client-python](https://github.com/qdrant/qdrant-client-python) |
| **Official PyPI Package** | [pypi.org/project/qdrant-client](https://pypi.org/project/qdrant-client/) (`1.19.0`) |
| **DevOps CLI Integration** | [`src/devops_cli/ai/rag/`](file:///workspaces/devops-cli/src/devops_cli/ai/rag/) • [`src/devops_cli/commands/ai.py`](file:///workspaces/devops-cli/src/devops_cli/commands/ai.py) |

---

## 2. General Information & Architecture

**Qdrant Client** is the official Python client library for Qdrant, a high-performance vector search engine written in Rust. It supports dense vector indexing, exact and Approximate Nearest Neighbors (ANN) via HNSW (Hierarchical Navigable Small World), payload filtering, and both local in-memory/disk storage and remote server connections.

In `devops-cli`:
- **RAG Grounding**: Powers the Retrieval-Augmented Generation (RAG) vector index under `.data/qdrant/`.
- **Knowledge Base Indexing**: Chunks and embeds repository documentation, architecture guides, and code symbols for semantic retrieval during code reviews.
- **Dual Mode**: Runs embedded locally (`QdrantClient(path=".data/qdrant")`) without requiring a separate server daemon, or connects to in-cluster Qdrant instances (`localhost:6333`).

---

## 3. Comparable Projects & Tradeoffs

| Vector DB | Strengths | Weaknesses | Why `devops-cli` Chose Qdrant Client |
| :--- | :--- | :--- | :--- |
| **`qdrant-client`** | Embedded local mode (no daemon required), high-speed Rust core, payload filtering, gRPC/REST support, single dependency. | Vector index files must be persisted to `.data/`. | **Selected**: The cleanest local + server dual-mode vector database in Python. |
| **`chromadb`** | Popular local vector store for Python prototyping. | Heavy dependency tree (includes SQLite, Clickhouse, ONNX), known lock contention on multi-process access. | Rejected: High binary footprint and slower indexing than Qdrant. |
| **`faiss`** (Meta) | Extreme raw vector indexing speed. | Difficult to install/build across platforms, no native metadata payload filtering, requires manual index file management. | Rejected: Too low-level, lacks structured metadata search. |
| **`pinecone` / `weaviate`** | Cloud-native hosted vector databases. | Requires external cloud accounts, proprietary APIs, cannot run offline in isolated air-gapped workstations. | Rejected: Violates offline workstation and zero-trust isolation rules. |

---

## 4. Key Concepts & Core Patterns

1. **Collections**: Named vector spaces configured with distance metrics (e.g. `Distance.COSINE`, `Distance.DOT`).
2. **PointStruct**: Represents a document chunk with unique ID, dense embedding vector (`list[float]`), and metadata payload (`path`, `text`, `category`).
3. **Payload Filtering**: Combines semantic similarity with structured metadata filters (e.g., filter by file extension or document category).
4. **Embedded vs Remote Connection**:
   - Local: `QdrantClient(path="./.data/qdrant")`
   - Remote: `QdrantClient(url="http://localhost:6333", grpc_port=6334)`

---

## 5. Common & Advanced Usage Examples

### Indexing Document Chunks in Qdrant
```python
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

client = QdrantClient(path="./.data/qdrant")
collection_name = "knowledge_base"

# Create collection if absent
if not client.collection_exists(collection_name):
    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=384, distance=Distance.COSINE),
    )

# Upsert vector points
points = [
    PointStruct(
        id=1,
        vector=[0.05] * 384,
        payload={"file": "docs/architecture.md", "text": "Microservice topology..."},
    )
]
client.upsert(collection_name=collection_name, points=points)
```

### Querying Relevant Context for Code Review
```python
def search_knowledge_base(client: QdrantClient, query_vector: list[float], top_k: int = 3):
    results = client.search(
        collection_name="knowledge_base",
        query_vector=query_vector,
        limit=top_k,
    )
    return [hit.payload["text"] for hit in results if hit.payload]
```

---

## 6. Best Practices & Security Standards

1. **Lazy Client Initialization**: Import `qdrant_client` only inside RAG command paths to keep general CLI boot time under 80ms.
2. **Data Directory Isolation**: Always place local database files under `.data/qdrant/` and include `.data/` in `.gitignore`.
3. **Handle Lock Files**: Handle SQLite/Qdrant lock exceptions gracefully if multiple CLI commands query the vector store simultaneously.
