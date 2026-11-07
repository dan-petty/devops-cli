# Proposal

## Why

Crawl4AI is a heavy pod (Chromium, 2.3 GB image) with many security advisories. When it is down, or when most fetches fail, the refine and alternatives jobs lose their page text and nothing shows it (#3893). The web search has alerts on `devops_cli_web_searches_total`. The page fetch has none.

## What Changes

- A new rule group `crawl4ai` in `k8s/monitoring/prometheus-values.yaml` holds two warning alerts.
- `Crawl4AIFetchesFailing` fires when at least 5 fetches of the roadmap Service through Crawl4AI failed in the last hour and more than half of the fetches of that hour failed. It reads `devops_cli_crawl4ai_fetches_total{job="roadmap-service"}`: a fetch with a `result` other than `ok` is a failure. It counts a series that starts in the hour from its first value, as the other rules of the Service do (#2505). The text names the label `result` and the two log commands.
- `Crawl4AIUnavailable` fires after 15 minutes in which Deployment `crawl4ai` wants a replica and has none available (`kube_deployment_status_replicas_available` below 1 while `kube_deployment_spec_replicas` is above 0). A Deployment that a person set to 0 replicas stays quiet.
- `k8s/README.md` lists both alerts in a new table in the section "Crawl4AI".
- The promtool fixture `tests/fixtures/prometheus_rules/crawl4ai_tests.yaml` and the tests in `tests/prometheus/test_k8s_monitoring_alerting.py` pin the rules.
- The change is a manifest that operators observe, so it carries the spec delta for the new capability `crawl4ai-alerts`.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `crawl4ai-alerts`: The alert rules for the fetches of the roadmap Service through Crawl4AI and for the Crawl4AI Deployment

### Modified Capabilities

None.

## Impact

- Manifests: `k8s/monitoring/prometheus-values.yaml`
- Tests: `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/fixtures/prometheus_rules/crawl4ai_tests.yaml` (new)
- Documents: `k8s/README.md`

## Feasibility

- The counter exists on `main`: `CRAWL4AI_FETCHES_TOTAL` in `src/devops_cli/telemetry/instruments.py` and `_markdown` in `src/devops_cli/ai/page_text.py` (read on 2026-11-07). It adds 1 per fetch that reaches the service, with `result` set to `ok`, an HTTP status or `error`. A page URL that the client refuses before a request does not count, so a bad model argument does not fire the alert.
- The Deployment `crawl4ai` exists in `k8s/devops/crawl4ai/deployment.yaml` with a readiness probe on `/health`, so `kube_deployment_status_replicas_available` follows its readiness.
- kube-state-metrics runs: the rules `RoadmapServiceUnavailable` and `MattermostUnavailable` already read its Deployment series. The default allow list in `tests/fixtures/k8s_monitoring/cluster_metrics/kube-state-metrics.yaml` keeps `kube_deployment_spec_replicas` and `kube_deployment_status_replicas_available`, and a test reads that list.
- The pinned promtool (`promtool test rules`) passes the unit tests of both rules. Before the rules existed, the new tests failed on `main` because the group `crawl4ai` did not exist.
- The Crawl4AI `/metrics` is not scraped: it needs the token (the issue says so).

## Existing Tool Considered

Prometheus rules in the existing values file, tested with promtool, as for the other alerts. No new tool and no new code. The change deletes no code.
