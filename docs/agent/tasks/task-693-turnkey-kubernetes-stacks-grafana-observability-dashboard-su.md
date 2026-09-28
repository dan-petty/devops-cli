# Task 693: Turnkey Kubernetes Stacks Grafana Observability Dashboard Suite (`k8s/monitoring/dashboards/`)

**Issue**: [#693](https://github.com/dan-petty/devops-cli/issues/693)
**Status**: Backlog
**Milestone**: `v0.2.24`
**Priority**: `priority/p0-critical`
**Scope**: `type/feature`, `scope/k8s`, `priority/p0-critical`

---

## 1. Description & Objectives

Each Kubernetes stack in `k8s/` operates as a dedicated microservice tier with specialized telemetry requirements. Providing turnkey, battle-tested Grafana dashboards pre-configured with PromQL queries, SLO alerts, and GitOps sidecar discovery ensures instant cluster observability.

#### Key Deliverables:
- Context & Rationale*: Each Kubernetes stack in `k8s/` operates as a dedicated microservice tier with specialized telemetry requirements. Providing turnkey, battle-tested Grafana dashboards pre-configured with PromQL queries, SLO alerts, and GitOps sidecar discovery ensures instant cluster observability.
- Complete Kubernetes Stack Dashboard Portfolio*:
- 1. **LLM Inference Fleet & Distributed Model Mesh (`k8s-llm-mesh.json`)**: Token generation throughput (tok/sec), Time-to-First-Token (TTFT), prompt processing latency, GPU KV cache memory utilization, tensor parallelism synchronization latency, request concurrency, queue depth, AWQ vs. TokenAttention throughput comparison across Ollama, LiteLLM, Portkey, vLLM, and LightLLM.
- 2. **AI Gateway & Failover Router (`k8s-ai-gateway.json`)**: LiteLLM and Portkey routing metrics, virtual model alias distributions (`devops-chat`, `devops-coder`, `devops-reasoning`, `devops-embedding`), routing distribution, circuit breaker trips, failover transitions, Valkey L2 cache hit ratios, and HTTP status codes (200, 429, 502, 503).
- 3. **ArgoCD GitOps & Fleet Orchestration (`k8s-argocd-gitops.json`)**: Application sync status (`Synced`, `OutOfSync`), sync duration histograms, controller reconciliation phase rates, git repository fetch latency and caching, application health states (`Healthy`, `Progressing`, `Degraded`), resource count per app, auto-sync and prune events, ArgoCD API server request latency and error rates.
- 4. **Cluster CoreDNS Resolution (`k8s-coredns.json`)**: Query latency percentiles (p50/p95/p99), request rates by protocol (UDP/TCP) and query type (A, AAAA, SRV, PTR), response code distributions (`NOERROR`, `NXDOMAIN`, `SERVFAIL`, `REFUSED`), DNS cache hit/miss ratios, upstream forwarder latency, plugin processing durations.
- 5. **NVIDIA GPU Acceleration & Hardware (`k8s-gpu-hardware.json`)**: Real-time GPU compute utilization (%), streaming multiprocessor (SM) occupancy, GPU memory (VRAM) allocated vs. total, GPU temperature and thermal throttling states, power draw (watts) vs. TDP limits, PCIe bus throughput, GPU Feature Discovery (GFD) label allocation and pod-to-GPU binding.
- 6. **Centralized Logging & Loki (`k8s-loki-logging.json`)**: Ingestion stream rates and bandwidth (MB/sec), chunk compression ratios, memory chunk pool utilization, query evaluation latency and throughput, storage write rates to volume storage, Promtail scrape targets, log line drops, error frequency breakdown by namespace (`llm`, `argocd`, `monitoring`, `squid`, `registry`).
- 7. **Prometheus Monitoring & Storage Engine (`k8s-prometheus-engine.json`)**: Target scraping latency and failure rates, active time-series count, head chunk allocation and TSDB block compaction durations, WAL writes and memory buffers, query execution durations, Alertmanager notification latency, rule group evaluation timing and alerting state tracking.
- 8. **OpenTelemetry Collector & Distributed Tracing (`k8s-otel-tracing.json`)**: OTel receiver span and metric ingestion rates, pipeline processor queue depth and memory ballast, exporter delivery latencies and HTTP retry rates, dropped span/metric counters, Jaeger/Tempo trace storage throughput, trace-to-metric exemplar links, sampling decision efficiency.
- 9. **Local OCI Container Registry (`k8s-registry.json`)**: Image push and pull throughput (MB/sec), image manifest and blob layer request rates, HTTP response codes (200, 201, 404, 500), storage volume capacity utilization, garbage collection runtime and reclaimed storage, catalog size and repository count.
- 10. **Squid Forward Proxy & Egress Perimeter (`k8s-squid-egress.json`)**: HTTP and HTTPS CONNECT egress request volume, client connection concurrency, bandwidth consumption (egress/ingress MB/sec), domain access classification (whitelisted vs. blocked), cache hit ratios for model weights and packages, DNS lookup latency via Squid helper, proxy response codes.
- GitOps Provisioning & Synchronization*: Integrated into `devops grafana dashboards sync`, packaging each stack dashboard as a labeled Kubernetes ConfigMap in `k8s/monitoring/dashboards/` for auto-reload by the Grafana sidecar.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
