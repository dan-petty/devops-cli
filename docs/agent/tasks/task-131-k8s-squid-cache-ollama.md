# Task 131: Deploy Kubernetes Squid Cache for Outbound Pods & 70B Ollama Models

**Issue**: [#131](https://github.com/dan-petty/devops-cli/issues/131)
**Status**: In Progress
**Milestone**: `v0.2.16`
**Priority**: `priority/p1-high`
**Scope**: `scope/k8s`

---

## 1. Description & Architectural Objectives

Configure and deploy a dedicated, high-capacity Squid caching forward proxy with SSL-Bump (TLS interception) into the Kubernetes cluster. The proxy is tailored to cache all outbound HTTP and HTTPS traffic from in-cluster workloads, with specialized tuning for multi-gigabyte Ollama 70B model downloads (~40GB–75GB per layer) from `registry.ollama.ai`.

### Key Architectural Requirements
1. **Massive Layer Object Sizing**:
   - `maximum_object_size 100 GB` (default 4MB bypasses large model weights).
   - `cache_dir ufs /var/spool/squid/cache 200000 16 256` (200GB disk cache backed by 250Gi PVC).
   - `maximum_object_size_in_memory 32 MB` to prevent container OOM when streaming multi-gigabyte layers.
2. **Range Requests & Resumed Pulls**:
   - `range_offset_limit -1` (forces Squid to fetch and cache full objects on range/chunked requests).
   - `quick_abort_min -1`, `quick_abort_max -1` (preserves background downloads if clients interrupt).
   - `read_ahead_gap 64 MB` for high-throughput streaming.
3. **SSL-Bump & Root CA Generation**:
   - Dynamic host certificate generator (`/usr/lib/squid/security_file_certgen`) with `/var/spool/squid/ssl_db`.
   - Internal Root CA (`squid-ca.pem`, `squid-ca.key`) stored in Kubernetes Secret and exported as ConfigMap for client pod trust.
   - Peek at SNI in step1, bump to decrypt, cache, and re-encrypt outbound requests.
4. **Content-Addressable Immutable Blob Caching**:
   - Aggressive refresh patterns for `/v2/.*/blobs/sha256:` and `registry.ollama.ai` (`override-expire override-lastmod ignore-no-cache ignore-no-store ignore-private ignore-reload`).
5. **Observability Features Enabled**:
   - Prometheus metrics scraping via `squid-exporter` sidecar on port `9301` (`/metrics`).
   - Cache Manager API access for `localhost` (`mgr:info`, `mgr:storedir`, `mgr:client_http_requests`).
   - Structured JSON logging to stdout (`logformat json_k8s`) for ingestion by Fluent Bit / Logfire / Loki.
   - SNMP port `3401` configuration.
6. **Failover & Resilience Architecture**:
   - High-availability readiness and liveness probes (`failureThreshold: 2`, `periodSeconds: 5`) for rapid endpoint isolation.
   - LFUDA dynamic aging eviction (`cache_replacement_policy heap LFUDA`) with watermarks (`cache_swap_low 85`, `cache_swap_high 92`) to protect 250Gi PVC from filling to 100%.
   - Content-addressable layer matching providing 100% offline immunity during upstream WAN outages.
   - Pod anti-affinity to prevent co-location of Squid instances on single nodes.
   - Comprehensive failover investigation documented in `docs/squid-failover-and-observability.md`.
7. **Workload & Ollama Integration**:
   - Injected `HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY`, and mounted `squid-ca.pem` into `/etc/ssl/certs/` in `k8s/llm/ollama-daemonset.yaml`.

---

## 2. Implementation Progress

- [x] Ground issue in GitHub tracking (#131) with milestone `v0.2.16`.
- [x] Create dedicated topic branch `feat/k8s-squid-cache`.
- [x] Create task tracking document `docs/agent/tasks/task-131-k8s-squid-cache-ollama.md`.
- [x] Create `docker/squid/entrypoint.sh` for SSL database and cache swap init.
- [x] Create `docker/squid/Dockerfile` using Ubuntu 24.04 and `squid-openssl`.
- [x] Create `docs/squid-failover-and-observability.md` detailing failover resilience and observability.
- [x] Create `k8s/squid/namespace.yaml` for dedicated `squid` namespace with baseline security.
- [x] Create `k8s/squid/configmap.yaml` with optimized `squid.conf` (100GB objects, SSL-Bump, JSON logging, LFUDA).
- [x] Create `k8s/squid/pvc.yaml` for 250Gi cache volume on `local-path`.
- [x] Create `k8s/squid/ca-secret.yaml` and `k8s/squid/ca-configmap.yaml` with Root CA certificates.
- [x] Create `k8s/squid/deployment.yaml` with `squid` + `squid-exporter` sidecar, probes, and anti-affinity.
- [x] Create `k8s/squid/service.yaml` exposing port 3128 (`http-proxy`) and port 9301 (`metrics`).
- [x] Create `k8s/squid/networkpolicy.yaml` governing pod ingress and internet egress.
- [x] Create `k8s/squid/kustomization.yaml` and update root `k8s/kustomization.yaml` and `k8s/namespaces.yaml`.
- [x] Update `k8s/llm/ollama-daemonset.yaml` with proxy environment and CA certificate mount.
- [x] Validate manifests via `kubectl apply --dry-run=client -k k8s/` (passed).
- [x] Validate manifests via `kubectl apply --dry-run=client -k k8s/squid/` (passed).
- [x] Author comprehensive test suite in `tests/test_k8s_squid.py` (6 tests passing).
