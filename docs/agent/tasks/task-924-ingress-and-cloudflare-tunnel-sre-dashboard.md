# Task: Ingress and Cloudflare Tunnel SRE Grafana Dashboard (#924)

**Issue**: [#924](https://github.com/dan-petty/devops-cli/issues/924)
**Status**: Done
**Milestone**: v0.2.25
**Priority**: priority/p1-high
**Scope**: scope/k8s

## Description
Cluster operators and SREs lacked a unified Grafana dashboard to monitor external ingress traffic through Traefik alongside the health, latency, throughput, and connection status of the Cloudflare Tunnel (`cloudflared`):

- **Missing Cloudflared Scraping**: While `cloudflared` ran with `--metrics 0.0.0.0:2000`, the pod template in `k8s/cloudflared/deployment.yaml` lacked Prometheus scrape annotations (`prometheus.io/scrape: "true"` and `prometheus.io/port: "2000"`).
- **Perimeter Network Policy Block**: `k8s/monitoring/networkpolicy.yaml` lacked an egress rule permitting Prometheus in the `monitoring` namespace to reach `cloudflared` on port 2000, causing connection attempts to be rejected by the network policy engine.
- **Dedicated SRE Ingress & Tunnel Dashboard**: No dashboard charted the Golden Signals for Traefik ingress (request rate, success/error percentages, latency percentiles p50/p95/p99, open connections, and per-service breakdown) together with Cloudflare Tunnel metrics (active HA connections, concurrent requests, smoothed QUIC RTT, and ingress/egress bandwidth).
- **Sidecar Auto-Provisioning**: The dashboard needed to be registered in `k8s/monitoring/dashboards/kustomization.yaml` under `grafana-stack-dashboards` for automatic sidecar loading.

## Key Changes
1. **Cloudflared Telemetry Scraping & Network Policy**:
   - Added `prometheus.io/scrape: "true"` and `prometheus.io/port: "2000"` annotations to `k8s/cloudflared/deployment.yaml`.
   - Added egress rule to `k8s/monitoring/networkpolicy.yaml` permitting TCP port 2000 egress to namespace `cloudflared`.
2. **Dedicated SRE Dashboard**:
   - Created `k8s/monitoring/dashboards/ingress-tunnel.json` (UID: `devops-ingress-tunnel`) featuring:
     - **Cloudflare Tunnel Health & Edge Connectivity**: Active HA connections gauge, concurrent tunnel requests, tunnel request rate, tunnel errors, QUIC smoothed RTT per connection/location, and tunnel network bandwidth (Rx/Tx).
     - **Traefik Ingress Traffic & Golden Signals**: Total ingress request rate, success rate %, error rate %, open entrypoint connections, status code distribution, and latency percentiles (p50, p95, p99).
     - **Backend Service Breakdown**: Request rate by backend service, 95th percentile service latency, service error rates (4xx/5xx), and open connections per service.
     - **Workload Resource Saturation**: Container CPU and memory working set metrics for Traefik and cloudflared pods.
3. **Sidecar Auto-Provisioning & Testing**:
   - Added `ingress-tunnel.json` to `grafana-stack-dashboards` in `k8s/monitoring/dashboards/kustomization.yaml`.
   - Updated `PROVISIONED["grafana-stack-dashboards"]` in `tests/test_k8s_monitoring_dashboards.py`.
   - Updated `test_monitoring_networkpolicy_specifics` in `tests/test_k8s_network_policies.py` to assert port 2000 egress.
   - Documented the dashboard in `k8s/README.md`.

## Acceptance Criteria
- [x] `cloudflared` deployment template has Prometheus scrape annotations and Prometheus actively scrapes port 2000.
- [x] `monitoring` NetworkPolicy permits port 2000 egress to `cloudflared`.
- [x] `ingress-tunnel.json` dashboard passes `devops grafana dashboards lint` with 0 errors and 0 warnings.
- [x] Dashboard is provisioned via `grafana-stack-dashboards` ConfigMap generator and loaded into live Grafana.
- [x] Unit and integration tests in `tests/test_k8s_monitoring_dashboards.py` and `tests/test_k8s_network_policies.py` pass.
- [x] `uv run devops ci` quality gates pass with 100% success.
