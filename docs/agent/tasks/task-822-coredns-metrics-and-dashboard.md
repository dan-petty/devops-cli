# Task: CoreDNS Metrics, Dashboard, and Alerting (#822)

**Issue**: [#822](https://github.com/dan-petty/devops-cli/issues/822)
**Scope**: scope/k8s
**Feasibility**: Confirmed against the live Prometheus server via `devops prometheus query`: `up{service="kube-dns"}` returns `1` (`job="integrations/kubernetes/kube-dns"`, `namespace="kube-system"`), `sum(rate(coredns_dns_requests_total[5m]))` returns `2.025`, and every panel query in `k8s/monitoring/dashboards/coredns.json` plus `sum(rate(coredns_dns_responses_total{job="integrations/kubernetes/kube-dns", rcode="SERVFAIL"}[5m])) / sum(rate(coredns_dns_responses_total{job="integrations/kubernetes/kube-dns"}[5m]))` returns live data.

## Description
Following `#1130` (which disabled the Prometheus server's `kubernetes-service-endpoints` job, enabled `clusterMetrics.kubeDNS` in `k8s/monitoring/k8s-monitoring-values.yaml`, and opened monitoring egress to `kube-system` port `9153`), `#822` delivers the CoreDNS metric capture, the `CoreDNS` Grafana dashboard (`k8s/monitoring/dashboards/coredns.json`, `uid: devops-coredns`), and the `CoreDnsServfailResponses` alert rule in `k8s/monitoring/prometheus-values.yaml`.

### Deliverables
- Live Prometheus query verification recorded:
  - `devops prometheus query 'up{service="kube-dns"}'` returns `1` with labels `app=kube-dns`, `container=coredns`, `job=integrations/kubernetes/kube-dns`, `namespace=kube-system`, `service=kube-dns`, `source=kubernetes`, `workload=ReplicaSet/coredns`.
  - `devops prometheus query 'sum(rate(coredns_dns_requests_total[5m]))'` returns `2.025`.
  - All five dashboard panel queries (`Requests by Type and Protocol`, `Responses by Rcode`, `Request Duration (p50 / p95 / p99)`, `Forward Request Duration (p50 / p95 / p99)`, and `Cache Hits and Misses`) return live series on the cluster.
- `tests/fixtures/metrics/coredns.yaml` captures the metric families, types, and label names served by `rancher/mirrored-coredns-coredns:1.12.0` on `kube-dns.kube-system.svc.cluster.local:9153/metrics`.
- `k8s/monitoring/dashboards/coredns.json` (`uid: devops-coredns`, provisioned via `grafana-stack-dashboards` in `k8s/monitoring/dashboards/kustomization.yaml`) charts DNS query rate by record type and protocol, response rate by rcode, request duration percentiles (`p50`/`p95`/`p99`), upstream forwarder duration percentiles (`p50`/`p95`/`p99`), and cache hits and misses over `job="integrations/kubernetes/kube-dns"`.
- `k8s/monitoring/prometheus-values.yaml` adds `CoreDnsServfailResponses` (`for: 5m`, `severity: warning`) to `homelab-services`, alerting when over 5% of CoreDNS responses over 5 minutes return `rcode="SERVFAIL"`.
- `tests/test_stack_dashboards.py`, `tests/test_k8s_monitoring_dashboards.py`, and `tests/test_k8s_monitoring_alerting.py` verify the CoreDNS scrape, dashboard provisioning, captured series/labels, and alert rule.

## Acceptance Criteria
- [x] `up{service="kube-dns"}` (`job="integrations/kubernetes/kube-dns"`) reads `1` through `devops prometheus query`, and `sum(rate(coredns_dns_requests_total[5m]))` returns a live value (`2.025`).
- [x] Every panel in `k8s/monitoring/dashboards/coredns.json` returns data on the cluster.
- [x] `tests/test_stack_dashboards.py` covers the CoreDNS metric names, label names, and single explicit scrape path (`_coredns_monitored`).
- [x] `tests/test_k8s_monitoring_alerting.py` verifies `CoreDnsServfailResponses` in `homelab-services` against `SERVED_SERIES`.
