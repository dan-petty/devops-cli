# Task 141: Resolve Squid Proxy Root CA, Build Image, and Enable Proxy Across K3s Cluster

**Issue**: [#141](https://github.com/dan-petty/devops-cli/issues/141)
**PR**: [#143](https://github.com/dan-petty/devops-cli/pull/143)
**Status**: In Review
**Milestone**: `v0.2.16`
**Priority**: `priority/p1-high`
**Scope**: `scope/k8s`

---

## 1. Description & Architectural Objectives

Fix and operationalize the in-cluster Squid forward caching proxy with SSL-Bump and Prometheus observability across the K3s homelab cluster.

### Problems & Remediation Steps
1. **Container Image**: Build `<registry-host>:30500/squid:0.2.16` containing `squid-openssl` and push to in-cluster registry.
2. **Cryptographic Root CA & Trust Distribution**:
   - Generate matching `ca.key` and `ca.pem` for SSL-Bump certificate generation.
   - Provision Secret `squid-ca-secret` in namespace `squid` (consumed by Squid container).
   - Provision ConfigMap `squid-ca-cert` in `squid` and `llm` namespaces (and update manifest declarations in `k8s/squid/ca-configmap.yaml` and `k8s/llm/ca-configmap.yaml`).
3. **Cluster Deployment & Health Verification**:
   - Apply `k8s/squid/` manifests (namespace, pvc, deployment, service, networkpolicy).
   - Verify Squid proxy pod and `squid-exporter` sidecar report `2/2 Running` with passing liveness and readiness probes.
   - Verify metrics endpoint `http://squid.squid.svc.cluster.local:9301/metrics`.
4. **Workload Proxy Enablement**:
   - Re-enable `HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY`, and CA certificate volume mount in `k8s/llm/ollama-daemonset.yaml`.
   - Update DaemonSet in cluster.
   - Validate outbound model pull proxying and caching.
5. **Quality Gates & Invariants**:
   - Update `tests/test_k8s_squid.py` to validate both the Squid deployment and the DaemonSet proxy integration.
   - Run `devops ci` (must pass 10/10 gates).

---

## 2. Implementation Progress

- [x] Ground issue in GitHub tracking (#141) under milestone `v0.2.16`.
- [x] Create task tracking document `docs/agent/tasks/task-141-squid-proxy-cluster-enablement.md`.
- [x] Build and push `<registry-host>:30500/squid:0.2.16` to in-cluster registry.
- [x] Generate matching Root CA keypair (`ca.key` and `ca.pem`).
- [x] Create Secret `squid-ca-secret` in `squid` namespace.
- [x] Synchronize `ca-configmap.yaml` in `k8s/squid/` and `k8s/llm/` with generated CA certificate.
- [x] Deploy `k8s/squid/` stack to K3s cluster.
- [x] Verify Squid pod readiness (`2/2 Running`) and metrics scraping (`:9301/metrics`).
- [x] Re-enable `HTTP_PROXY` and `squid-ca-cert` volume mount in `k8s/llm/ollama-daemonset.yaml`.
- [x] Apply updated DaemonSet to cluster and verify Ollama pods restart cleanly.
- [x] Verify outbound proxying through Squid and cache hit generation.
- [x] Run `devops ci` to ensure 100% compliance across all 10 quality gates.
