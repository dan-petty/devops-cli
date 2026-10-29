# Proposal

## Why

Issue #2094: the cache Valkey keeps at most 1536 MiB of data, with `--maxmemory-policy noeviction` (#711). At the bound, Valkey refuses each write, and Open WebUI cannot keep its session and task state. No alert fires before that: `ValkeyCacheErrors` fires on a down exporter or a rejected connection, not on a refused write.

## What Changes

- A new alert group, `valkey-memory`, in `k8s/monitoring/prometheus-values.yaml`, after `homelab-services`, which holds `ValkeyCacheErrors`. It has one rule:
  - `ValkeyMemoryNearBound` fires with the severity `warning` when a Valkey whose policy is `noeviction` keeps its data above 80% of its `maxmemory` for 10 minutes. It names the namespace, the job and the instance of the exporter.
- The rule selects a Valkey by the policy that its exporter reports, not by its job. Today the cache Valkey (`llm/valkey`) is the only exported Valkey with `noeviction` and a bound. The run index (`llm/valkey-runs`) has the same policy but no exporter, so the rule covers it when it gets one. devops-cli's cache Valkey (`llm/valkey-devops`) evicts at its bound, and Argo CD's Redis has no bound, so the rule never fires for them.
- `tests/test_k8s_monitoring_alerting.py` pins the rule, adds its three series to the served series, and runs `promtool test rules` on `tests/fixtures/prometheus_rules/valkey_memory_tests.yaml`.
- The Alerting table in `k8s/README.md` lists the alert, and the cache Valkey section names it.
- An alert rule is behavior that a person sees, so the change carries a spec delta: an ADDED requirement of `llm-valkey`.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `llm-valkey`: an alert fires before a Valkey that refuses writes at its bound reaches it.

## Impact

- `k8s/monitoring/prometheus-values.yaml`, `k8s/README.md`.
- `tests/test_k8s_monitoring_alerting.py`, `tests/fixtures/prometheus_rules/valkey_memory_tests.yaml`.
- Alertmanager has no receiver until the webhook Secret exists, so the alert shows in Grafana's Alerting view and notifies no one until then.

## Feasibility

- The live Prometheus server, queried through Grafana on 2026-10-29, holds `redis_memory_used_bytes` and `redis_memory_max_bytes` from the `redis-exporter` sidecar (`oliver006/redis_exporter` v1.93.0) of three targets. `job="valkey"` (namespace `llm`) has a max of 1610612736 bytes (1536 MiB) and uses 1427432 bytes. `job="valkey-devops"` has a max of 100663296 bytes (96 MiB). `job="argocd-redis-metrics"` (namespace `argocd`) has a max of 0.
- `redis_instance_info` carries the label `maxmemory_policy`: `noeviction` for `valkey` and `argocd-redis-metrics`, `allkeys-lru` for `valkey-devops`. The ratio of used to max is `+Inf` for Argo CD's Redis, so the rule needs a guard for a max of 0.
- The rule's expression, run live without its threshold, returns one series, `job="valkey"`, at 0.00089. With the threshold of 0.8 it returns no series.
- `k8s/llm/valkey-runs.yaml` has no exporter sidecar and no scrape annotation.
- `promtool` 3.15.0 (on PATH, as the existing rule tests use it) accepts the rule, and `promtool test rules` passes the new unit tests.

## Existing Tool Considered

Prometheus alerting rules, the redis_exporter series that the cluster already scrapes, and `promtool test rules`, which the repository already uses, cover the need. Nothing new is built, and no code is deleted.
