# Task 646: Homelab Kubernetes Platform Enhancements, Cloudflare Tunnel GitOps, Ingress Automation & AI Triage

**Issue**: [#646](https://github.com/dan-petty/devops-cli/issues/646)
**Status**: Done
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
   - Deferred to dedicated v0.2.24 deliverable `devops k8s doctor` (#408).

3. **Homelab SecOps & Policy-as-Code Integration**:
   - Tracked across v0.2.25 deliverables for runtime Falco/Tetragon and Kyverno admission policy validation.

4. **IDE Assistant Interoperability**:
   - Tracked under v0.2.25 deliverable `Automated Multi-IDE MCP Scaffolder` (`devops ide configure`).

### Key Deliverables:
- [x] **Declarative Cloudflare Tunnel Manifests** (`k8s/cloudflared/`):
  - Deployment with non-root security context, token secret references, metrics endpoint on port 2000, and liveness/readiness probes.
  - Kustomization and NetworkPolicy isolating tunnel ingress/egress.
- [x] **Cluster Ingress Manifests & Values** (`k8s/ingress/`):
  - Traefik Helm values configured with `service.type: ClusterIP`.
  - Kubernetes `Ingress` manifests for `open-webui`, `llm-gateway`, `kube-prometheus-grafana`, and `argocd-server`.
- [x] **Namespaces & Zero-Trust Documentation** (`k8s/namespaces.yaml`, `k8s/README.md`):
  - Added `cloudflared` namespace with restricted pod security standards, root kustomization integration, and end-to-end routing setup guide.
- [x] **Gated CI Compliance & Architectural Invariants**:
  - Comprehensive unit test coverage with structural tuple assertions adhering to $M \le 10$ complexity caps.
