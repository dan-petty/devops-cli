# Task 564: Review, Findings and AI Spend Metrics Reach Prometheus

**Issue**: [#564](https://github.com/dan-petty/devops-cli/issues/564)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p2-medium`
**Scope**: `type/bug`, `scope/telemetry`, `priority/p2-medium`

---

## 1. Description & Objectives

Found while fixing #547. With telemetry reaching the collector, the `devops-cli.json` and
`ai-spend.json` dashboards still queried metrics nothing sent over OTLP:
- `devops_cli_review_duration_seconds` and `devops_cli_findings_total` were emitted nowhere;
- `devops_cli_ai_spend_usd_total`, `devops_cli_ai_requests_total`,
  `devops_cli_ai_server_spend_usd` and `devops_cli_ai_active_servers` existed only as Prometheus
  text on `devops server`'s `/metrics`, which nothing in the cluster scrapes.

Every metric was also sent as a gauge. Counters and histograms therefore could not accumulate:
each command is its own short-lived process, so no process holds a running total.
`increase(devops_cli_command_total[1h])` read a constant 1. And because the process id was in
the resource, each command started a new stream.

### Key Deliverables Completed:

- [x] **Counters and histograms as deltas** (`telemetry/tracer.py`):
  - `increment_counter` sends a monotonic delta sum;
  - `record_histogram` sends a delta histogram with explicit buckets;
  - `record_metric` stays a gauge.

  Metrics carry a host resource: `service.instance.id` is the host name, which Prometheus
  stores as `instance`. The process id and version are left out, so one host's commands add to
  one series.
- [x] **The collector adds them up**: the `deltatocumulative` processor (`max_stale: 1h`) runs
  before remote write (`k8s/otel/values.yaml`).
- [x] **One list of sent metrics** (`telemetry/instruments.py`): commands, reviews, findings,
  AI requests, tokens, spend, and RAG query time, each with its kind, unit and description.
  `docs/TELEMETRY.md` is generated from it. The old table named six metrics nothing emitted.
- [x] **Reviews** send their wall time by target type, and their findings by persona, severity
  and status.
- [x] **AI calls** count, as they happen, by provider, model, server and serving backend:
  - requests, and whether the cache answered;
  - prompt and completion tokens;
  - approximate spend.
- [x] **Dashboards** read only sent metrics:
  - active backends are those that served an uncached call in the last 15 minutes;
  - spend by backend sums `devops_cli_ai_spend_usd_total`;
  - total tokens sums both types.
- [x] **Automated Tests & Quality Gates** (`tests/test_telemetry_instruments.py`):
  - every query in both dashboards names a sent series;
  - counter payload shape and host resource;
  - histogram buckets;
  - AI call metrics by backend, cached calls included;
  - review duration and findings counts;
  - the collector pipeline;
  - backend names.

  100% passing status across Gated CI validation suite (`uv run devops ci`).

### Not verified in the cluster

The collector change was checked by parsing its values, not deployed. After merge:
1. Upgrade the collector release with `k8s/otel/values.yaml`.
2. Run a review with telemetry connected.
3. Check the dashboards' review, findings and spend panels.
