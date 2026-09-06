# Knowledge Base: Valkey (Open-Source In-Memory Data Store & Cache)

## 1. Overview & Purpose

Valkey is a high-performance, open-source (BSD-3-Clause) key-value data store developed under the Linux Foundation as the community-driven continuation of Redis. It provides sub-millisecond in-memory data storage, rich data structures, caching, pub/sub messaging, and distributed coordination.

In the `devops-cli` ecosystem, Valkey serves as:
- **Workstation & Cluster In-Memory Cache**: Powers GitOps state caching for ArgoCD in the `argocd` namespace and in-memory cache for local LLM inference services in the `llm` namespace.
- **Distributed Embedding & Review Cache Tier**: Provides high-throughput SHA-256 keyed cache storage for dense text embeddings and multi-persona AI code review findings, eliminating redundant LLM calls across workstations and CI runners.
- **Distributed Rate Limiting & Token Bucket**: Enforces cross-process concurrency limits to protect local GPUs (Ollama) from VRAM exhaustion and prevent HTTP 429 throttling against cloud AI provider APIs.
- **Agent Pub/Sub & Event Streaming**: Backing store for event distribution across continuous file watchers (`devops ai review path --watch`) and agent coordination loops.

---

## 2. Architecture & Key Features

### Valkey 8.0+ Engine Enhancements
- **Asynchronous I/O Threading**: Enhanced multi-threaded event processing delivering higher throughput and lower tail latency under concurrent client workloads.
- **Protocol Compatibility**: Full RESP2 and RESP3 wire protocol support, ensuring seamless drop-in compatibility with established `redis-py` and modern `valkey-py` client libraries.
- **Open-Source Governance**: True open-source licensing (BSD-3-Clause) under the Linux Foundation, avoiding vendor lock-in, proprietary licensing restrictions, or dual-license ambiguity.
- **Data Structures**: Native support for Strings, Hashes, Lists, Sets, Sorted Sets, HyperLogLog, Geospatial indexes, Bitmaps, and Streams (`XADD`, `XREADGROUP`).

### Deployment Topologies in DevOps CLI
1. **Local Workstation Minikube**:
   - Deployed as `valkey/valkey:8.0-alpine` via declarative manifests in `k8s/llm/valkey.yaml` and Helm values in `k8s/argocd/values.yaml`.
   - Exposed on standard port `6379` with automated service URL detection (`valkey.url`) and port-forwarding management (`devops k8s port-forward --valkey-port 6379`).
2. **Ephemeral Testing Sandbox**:
   - Ephemeral rootless containers via `Testcontainers` / Docker sandbox fixtures for offline integration tests without cluster dependencies.
3. **Enterprise Production Cluster**:
   - Valkey Sentinel for automated master failover and Valkey Cluster for horizontal data sharding across workstation fleets.

---

## 3. Operational & CLI Reference

### Workstation CLI Commands
```bash
# Verify connectivity and measure round-trip latency to Valkey
devops valkey ping

# View structured server metrics, memory fragmentation, and keyspace statistics
devops valkey info

# View Rich terminal dashboard of hit rates, ops/sec, and memory distribution
devops valkey stats

# Search active cache keys matching a pattern
devops valkey keys --pattern "ai:cache:*"

# Read or write key values with TTL
devops valkey get "ai:cache:embedding:a1b2c3d4"
devops valkey set "config:override" "true" --ttl 3600

# Flush cache namespace safely
devops valkey flush --namespace "ai:cache"

# Drop into interactive valkey-cli session
devops valkey cli
```

### Kubernetes Cluster Diagnostics
```bash
# Check Valkey deployment and pod health in llm namespace
kubectl -n llm get pods -l app=valkey

# Execute ping check inside Minikube cluster
kubectl -n llm exec -it svc/valkey -- valkey-cli ping

# Inspect memory usage and client connections
kubectl -n llm exec -it svc/valkey -- valkey-cli info memory
kubectl -n llm exec -it svc/valkey -- valkey-cli info clients
```

---

## 4. Python Integration & Caching Architecture

### Async Client Integration (`valkey-py`)
```python
import asyncio
from typing import Any
import valkey.asyncio as valkey


class ValkeyCacheProvider:
    """High-performance async Valkey cache provider for AI review findings and embeddings."""

    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0) -> None:
        self.client = valkey.Valkey(
            host=host,
            port=port,
            db=db,
            decode_responses=True,
            socket_timeout=2.0,
            socket_connect_timeout=2.0,
        )

    async def ping(self) -> bool:
        """Verify Valkey connectivity."""
        try:
            return bool(await self.client.ping())
        except Exception:
            return False

    async def get_embedding(self, chunk_sha256: str) -> list[float] | None:
        """Retrieve cached embedding vector by SHA-256 hash."""
        import json

        data = await self.client.get(f"emb:{chunk_sha256}")
        if data:
            return json.loads(data)
        return None

    async def set_embedding(self, chunk_sha256: str, vector: list[float], ttl: int = 86400) -> None:
        """Cache embedding vector with TTL."""
        import json

        await self.client.set(f"emb:{chunk_sha256}", json.dumps(vector), ex=ttl)
```

---

## 5. Security & Zero-Trust Best Practices

1. **Network Isolation & SSRF Mitigation**:
   - Bind Valkey to loopback (`127.0.0.1`) or private Kubernetes cluster networks (`svc.cluster.local`).
   - Validate destination endpoints with `is_safe_endpoint()` to prevent SSRF vulnerabilities.
2. **Authentication & ACLs**:
   - When exposed outside container namespaces, enforce strong password authentication (`requirepass`) or Valkey ACL rules (`auth <user> <pass>`).
   - Never commit plaintext Valkey passwords into Git repositories; store credentials in OS Keyring (`devops config keyring set valkey.password <token>`).
3. **Resource Bounding & Eviction Policies**:
   - Always configure explicit memory limits (`maxmemory 512mb`) and cache eviction policies (`maxmemory-policy allkeys-lru` or `volatile-lru`) to prevent OOM termination of workstation nodes.
4. **Command Renaming & Disabling**:
   - In shared environments, disable or rename dangerous commands (`FLUSHALL`, `CONFIG`, `DEBUG`, `KEYS`) in `valkey.conf`.
