# Task 646: Homelab Kubernetes Platform Enhancements, Cloudflare Tunnel GitOps, Ingress Automation & AI Triage

**Issue**: [#646](https://github.com/dan-petty/devops-cli/issues/646)
**Status**: In Progress
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/k8s`, `priority/p1-high`

---

## 1. Description & Objectives

Incorporate comprehensive homelab Kubernetes platform enhancements into `devops-cli` covering foundation routing, platform engineering, runtime SecOps, and AI-assisted cluster operations:

1. **Cloudflare Tunnel & Ingress Automation (Zero-Touch Wildcard Routing)**:
   - Declarative `cloudflared` multi-replica deployment manifest under `k8s/cloudflared/` with non-root security context (`runAsUser: 65532`, `readOnlyRootFilesystem: true`), token secret references, and health probes.
   - Internal Cluster Ingress Controller (Traefik / Ingress-Nginx) deployed as an internal `ClusterIP` service, allowing Cloudflare Tunnel to pass traffic directly without cloud load balancers or public port exposure.
   - Standard Kubernetes `Ingress` definitions for cluster workloads (`open-webui`, `llm-gateway`, `kube-prometheus-grafana`, `argocd-server`) supporting wildcard `*.homelab.<domain>` routing with client host-header preservation.

2. **AI DevOps Cluster Incident Triage (`devops k8s triage` / `k8s_triage`)**:
   - In-cluster AI incident analysis integrating cluster events, pod failure logs (`CrashLoopBackOff`, `OOMKilled`, probe timeouts), and network policy rejections with the local LiteLLM / Ollama gateway.
   - FastMCP tool (`k8s_triage`) allowing AI agents to diagnose cluster health and recommend remediation.

3. **Homelab SecOps & Policy-as-Code Integration**:
   - Kyverno admission policy validation in `devops scan` for cluster breakout mitigation and privilege escalation prevention.
   - Trivy / Harbor container image vulnerability gating and Cosign signature verification (`devops secops verify-image`).
   - eBPF runtime event analysis (Falco / Tetragon) via Loki log streaming and alert correlation.

4. **IDE Assistant Interoperability**:
   - `devops ai export-config --target continue` command generating Continue.dev configuration pointing to the cluster's authenticated LLM Gateway.

### Key Deliverables:
- [x] **Declarative Cloudflare Tunnel Manifests** (`k8s/cloudflared/`):
  - Deployment with non-root security context, token secret references, metrics endpoint on port 2000, and liveness/readiness probes.
  - Kustomization and NetworkPolicy isolating tunnel ingress/egress.
- [x] **Cluster Ingress Manifests & Values** (`k8s/ingress/`):
  - Traefik Helm values configured with `service.type: ClusterIP`.
  - Kubernetes `Ingress` manifests for `open-webui`, `llm-gateway`, `kube-prometheus-grafana`, and `argocd-server`.
- [ ] **AI DevOps Incident Triage Engine** (`src/devops_cli/commands/k8s/triage.py`, `src/devops_cli/ai/tools/k8s_triage.py`):
  - Extract failed pod logs and Kubernetes events, synthesize incident summaries via LLM Gateway, and output actionable root-cause diagnoses.
- [ ] **IDE Configuration Generator** (`src/devops_cli/commands/ai/export_config.py`):
  - Export Continue.dev and Open-WebUI model connection templates bound to `llm-gateway`.
- [x] **Gated CI Compliance & Architectural Invariants**:
  - Comprehensive unit test coverage with structural tuple assertions adhering to $M \le 10$ complexity caps.
