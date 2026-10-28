---
applies_to:
  - "tool:prometheus@3.2.*"
sources:
  - "https://prometheus.io/"
  - "https://github.com/prometheus/prometheus"
reviewed: "2026-10-15"
tags:
  - "prometheus"
  - "metrics"
  - "observability"
---

# Knowledge Base: Prometheus (Metrics Collection & PromQL Engine)

## 1. Overview & Purpose

Prometheus is an open-source systems monitoring and alerting toolkit. It collects and stores metrics as time series data identified by metric names and key/value pairs (labels). In the `devops-cli` ecosystem, Prometheus scrapes metrics exposed by the DevOps REST engine (`/metrics`), Kubernetes node metrics, container runtimes, and application workloads.

---

## 2. Usage Information & Architecture

- **Pull Model Scraper**: Periodically scrapes configured HTTP endpoints (`/metrics`) formatted according to the OpenMetrics / Prometheus exposition format.
- **PromQL Query Engine**: Flexible query language for computing percentiles, rates of change (`rate()`, `irate()`), aggregations (`sum()`, `avg()`), and histogram distributions.
- **Client SDK**: `devops_cli` sends its metrics over OTLP to the OpenTelemetry Collector, which writes them to Prometheus. `INSTRUMENTS` in `src/devops_cli/telemetry/instruments.py` declares each one, and `docs/TELEMETRY.md` lists them, including:
  - `devops_cli_command_total`: Total count of executed CLI commands.
  - `devops_cli_command_duration_seconds`: Histogram of command execution latencies.
  - `devops_cli_subprocess_duration_seconds`: Histogram of subprocess execution durations by binary and status.
  - `devops_cli_subcommand_duration_seconds`: Histogram of subcommand durations by subcommand and status.
- **CLI Subcommand**: `devops prometheus` provides PromQL querying, target health inspection, and query execution.

---

## 3. Common & Advanced Commands

### DevOps CLI Prometheus Commands
```bash
# Execute PromQL query against Prometheus server
devops prometheus query "rate(devops_cli_command_total[5m])"

# Check status of scrape targets and reachability
devops prometheus targets

# List recording and alerting rules
devops prometheus rules
```

### Standard PromQL Queries & Commands
```bash
# Port-forward Prometheus server to local port 9090
kubectl port-forward svc/prometheus-server -n monitoring 9090:80

# Query command execution rate per second over 5 minutes
curl -G 'http://localhost:9090/api/v1/query' \
  --data-urlencode 'query=sum(rate(devops_cli_command_total[5m])) by (command)' | jq .

# Compute 95th percentile execution duration (a native histogram: no _bucket series, no le label)
curl -G 'http://localhost:9090/api/v1/query' \
  --data-urlencode 'query=histogram_quantile(0.95, sum(rate(devops_cli_command_duration_seconds[5m])))' | jq .

# Scrape local devops REST service directly
curl -s http://localhost:8000/metrics
```

### Sample Prometheus Exposition Format
```text
# HELP devops_cli_command_total Total count of executed CLI commands.
# TYPE devops_cli_command_total counter
devops_cli_command_total{command="serve",status="ok"} 42
devops_cli_command_total{command="review",status="ok"} 18

# HELP devops_cli_command_duration_seconds CLI command execution duration in seconds.
# TYPE devops_cli_command_duration_seconds histogram
devops_cli_command_duration_seconds_bucket{le="0.05"} 12
devops_cli_command_duration_seconds_bucket{le="0.1"} 28
devops_cli_command_duration_seconds_bucket{le="+Inf"} 60
devops_cli_command_duration_seconds_sum 4.82
devops_cli_command_duration_seconds_count 60
```

---

## 4. Best Practice Guidance

1. **Use `rate()` Over `irate()` for Alerting**: Use `rate()` over bounded time ranges (`[5m]`) for alerting rules and Grafana queries to smooth out temporary jitter.
2. **Label Cardinality**: Avoid dynamic high-cardinality values (e.g. user IDs, UUIDs, full URLs) in metric label values to prevent memory bloat in the Prometheus TSDB.
3. **Histogram Buckets**: Define histogram buckets tailored to expected latency boundaries (e.g. `0.005`, `0.01`, `0.025`, `0.05`, `0.1`, `0.25`, `0.5`, `1.0`, `2.5`, `5.0`, `10.0`).
4. **Retention Policies**: Configure appropriate storage retention (`--storage.tsdb.retention.time=15d`) to balance historical tracking with disk utilization.

---

## 5. Security Recommendations & Zero-Trust Policies

- **Endpoint Protection**: When exposing `/metrics` across public networks, secure the endpoint with TLS and mutual authentication or IP whitelisting.
- **No Sensitive Data in Labels**: Never include passwords, tokens, API keys, or personally identifiable information (PII) in metric names or label dimensions.

---

## 6. General Standards & Reference Guidelines

- **Port Convention**: Standard Prometheus service port `9090` (or `80` via Kubernetes Service abstraction).
- **Metric Naming**: Follow standard OpenMetrics naming conventions (`<namespace>_<subsystem>_<name>_<unit>`).

---

## 7. Official References & Published Artifacts

- **Project Homepage**: [prometheus.io](https://prometheus.io/)
- **Public Git Repository**: [github.com/prometheus/prometheus](https://github.com/prometheus/prometheus)
- **Published Container Image**: [hub.docker.com/r/prom/prometheus](https://hub.docker.com/r/prom/prometheus)
- **DevOps CLI Prometheus Engine**: [src/devops_cli/commands/prometheus.py](../../../../commands/prometheus.py)
