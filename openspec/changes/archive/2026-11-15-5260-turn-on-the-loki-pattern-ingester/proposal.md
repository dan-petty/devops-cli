# Proposal

## Why

The Loki pattern ingester was off, so the Patterns tab of Logs Drilldown was empty and `query_loki_patterns` returned HTTP 404. An agent then reads many log lines where a few templates with counts would show the shape of an error (#5260).

## What Changes

- Set `loki.pattern_ingester.enabled: true` in `k8s/logging/loki-values.yaml`. Pattern persistence stays off, so the patterns serve triage for 3 hours.
- Add `tests/k8s/test_loki_pattern_ingester.py`: `helm template` of chart 21.2.1 writes `pattern_ingester.enabled: true` into the Loki configuration.

## Capabilities

### New Capabilities

- `loki-patterns`: the pattern ingester of the logging stack.

### Modified Capabilities

None.

## Impact

- Manifests: `k8s/logging/loki-values.yaml`
- Tests: `tests/k8s/test_loki_pattern_ingester.py`

## Feasibility

- Read on `origin/main`, 2026-11-15. `k8s/logging/loki-values.yaml` is the Monolithic Loki of chart `grafana-community/loki` 21.2.1.
- `helm template loki loki --repo https://grafana-community.github.io/helm-charts --version 21.2.1 -f k8s/logging/loki-values.yaml` writes `pattern_ingester: enabled: true`.
- The `all` target includes the pattern ingester, and it adds no pod and no egress.
- `uv run pytest tests/k8s/test_loki_pattern_ingester.py` passes after the change.

## Existing Tool Considered

The Loki pattern ingester is part of Loki v3.7.9, and Logs Drilldown 3.1.0 reads it. The change is three lines of values: about 200 tokens to build and 20 a quarter to keep.

## Dependencies

None.
