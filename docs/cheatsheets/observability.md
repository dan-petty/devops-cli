# Observability & GitOps Tool Cheatsheet

Compare native REST API calls and CLI utilities for Prometheus, Grafana, and ArgoCD with unified `devops-cli` commands with SSRF mitigation and OS Keyring integration.

---

## 1. Prometheus Metrics & PromQL

| Action / Goal | Original Command (`curl` / `promtool`) | `devops-cli` Command | Key Enhancements in `devops-cli` |
| :--- | :--- | :--- | :--- |
| **Instant PromQL Query** | `curl -G "http://localhost:8090/api/v1/query" --data-urlencode "query=up"` | `devops prometheus query "up"` | Automatically resolves active Prometheus endpoint, formats metric vectors as Rich tables, and handles SSRF validation. |
| **Query Range Matrix** | `curl -G "http://localhost:8090/api/v1/query_range" ...` | `devops prometheus range "node_cpu_seconds_total" --step 1m` | Fetches time series ranges and renders ASCII metric progression trends. |
| **Check Prometheus Targets** | `curl "http://localhost:8090/api/v1/targets"` | `devops prometheus targets` | Summarizes scraped endpoint health, scrape duration, and last error messages. |

---

## 2. Grafana Dashboards & Authentication

| Action / Goal | Original Command (`grafana-cli` / `curl`) | `devops-cli` Command | Key Enhancements in `devops-cli` |
| :--- | :--- | :--- | :--- |
| **List Dashboards** | `curl -H "Authorization: Bearer <token>" "http://localhost:8030/api/search"` | `devops grafana dashboards` | Retrieves Grafana token securely from OS Keyring, parses dashboard metadata, and formats title/tags/UID tables. |
| **Export Dashboard JSON** | `curl -H "Authorization: Bearer <token>" "http://localhost:8030/api/dashboards/uid/<uid>"` | `devops grafana export <uid> [--output <file>]` | Exports dashboard JSON schema with sanitized credentials and formatted indentation. |

---

## 3. ArgoCD Application GitOps Sync

| Action / Goal | Original Command (`argocd`) | `devops-cli` Command | Key Enhancements in `devops-cli` |
| :--- | :--- | :--- | :--- |
| **List Applications** | `argocd app list --insecure` | `devops argo list` | Displays application sync status, health status, target revision, and destination cluster/namespace. |
| **Sync Application** | `argocd app sync <app_name> --prune` | `devops argo sync <app_name>` | Triggers GitOps reconciliation with automated health polling and rollback warnings. |
| **Inspect App Status** | `argocd app get <app_name>` | `devops argo status <app_name>` | Detailed tree view of synced Kubernetes resources, live manifests, and Git sync diffs. |
