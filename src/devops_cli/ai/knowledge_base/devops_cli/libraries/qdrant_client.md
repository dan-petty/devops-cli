# Code Library: Qdrant Client (Vector Embeddings & Semantic Search)

## 1. Project References

| Resource | Endpoint / URL |
| :--- | :--- |
| **Official Documentation** | [qdrant.tech/documentation](https://qdrant.tech/documentation/) |
| **Public Git Repository** | [github.com/qdrant/qdrant-client-python](https://github.com/qdrant/qdrant-client-python) |
| **Official PyPI Package** | [pypi.org/project/qdrant-client](https://pypi.org/project/qdrant-client/) (`1.19.1`) |
| **DevOps CLI Integration** | [`src/devops_cli/ai/rag/`](../../../../../../src/devops_cli/ai/rag/) • [`src/devops_cli/commands/ai.py`](../../../../../../src/devops_cli/commands/ai.py) |

---

## 2. General Information & Architecture

**Qdrant Client** is the official Python client library for Qdrant, a high-performance vector search engine written in Rust. It supports dense vector indexing, exact and Approximate Nearest Neighbors (ANN) via HNSW (Hierarchical Navigable Small World), payload filtering, and remote server connections.

In `devops-cli`:
- **RAG Grounding**: Powers the Retrieval-Augmented Generation (RAG) vector index.
- **Knowledge Base Indexing**: Chunks and embeds repository documentation, architecture guides, and code symbols for semantic retrieval during code reviews.
- **Server Connection**: Connects to a Qdrant server by URL (`qdrant.url`, or the in-cluster `llm/qdrant` service via the Kubernetes API proxy); no embedded mode is used; `.data/rag/` holds only the local index cache.

---

## 3. Comparable Projects & Tradeoffs

| Vector DB | Strengths | Weaknesses | Why `devops-cli` Chose Qdrant Client |
| :--- | :--- | :--- | :--- |
| **`qdrant-client`** | High-speed Rust core, payload filtering, gRPC/REST support, single dependency. | Requires running Qdrant service. | **Selected**: The cleanest vector database client in Python. |
| **`chromadb`** | Popular local vector store for Python prototyping. | Heavy dependency tree (includes SQLite, Clickhouse, ONNX), known lock contention on multi-process access. | Rejected: High binary footprint and slower indexing than Qdrant. |
| **`faiss`** (Meta) | Extreme raw vector indexing speed. | Difficult to install/build across platforms, no native metadata payload filtering, requires manual index file management. | Rejected: Too low-level, lacks structured metadata search. |
| **`pinecone` / `weaviate`** | Cloud-native hosted vector databases. | Requires external cloud accounts, proprietary APIs, cannot run offline in isolated air-gapped workstations. | Rejected: Violates offline workstation and zero-trust isolation rules. |

---

## 4. Key Concepts & Core Patterns

1. **Collections**: Named vector spaces configured with distance metrics (e.g. `Distance.COSINE`, `Distance.DOT`).
2. **PointStruct**: Represents a document chunk with unique ID, dense embedding vector (`list[float]`), and metadata payload (`path`, `text`, `category`).
3. **Payload Filtering**: Combines semantic similarity with structured metadata filters (e.g., filter by file extension or document category).
4. **Server Connection**: `QdrantClient(url=settings.qdrant.url)`

---

## 5. Common & Advanced Usage Examples

### Indexing Document Chunks in Qdrant
```python
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

client = QdrantClient(url="http://example.internal:6333")
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

1. **Lazy Client Initialization**: Import `qdrant_client` only inside RAG command paths to keep general CLI cold-start latency low.
2. **Cache Directory Isolation**: Local index cache lives under `.data/rag/` and is ignored by git.
3. **Connection Handling**: Handle network and connection exceptions gracefully if the Qdrant service is unreachable.
