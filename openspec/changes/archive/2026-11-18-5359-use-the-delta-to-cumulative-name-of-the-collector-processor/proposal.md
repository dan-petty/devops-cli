# Proposal: #5359

## Why

The OpenTelemetry collector logs a deprecation warning at start for the processor name that
`k8s/otel/values.yaml` uses:

```
warn builders/builders.go:40 "deltatocumulative" alias is deprecated; use "delta_to_cumulative" instead
```

The contrib project renamed the component type `deltatocumulative` to `delta_to_cumulative` and
keeps the old name as an alias. When a later collector version removes the alias, the collector does
not start, and all metrics, spans and logs of the OTLP path stop. Closes #5359.

## What Changes

- `k8s/otel/values.yaml` uses `delta_to_cumulative` as the processor key and in the metrics
  pipeline, with the comments that name it.
- The dashboard, the documents, their generator, the code comments and the tests that name the
  processor or its `otelcol_delta_to_cumulative_datapoints` metric follow the rename.

## Capabilities

- `command-telemetry` (modified): the transform processor runs before `delta_to_cumulative`.
- `monitoring-collectors` (modified): the `delta_to_cumulative` processor sets `max_stale` to `1h`.

## Impact

- The collector starts with no deprecation warning, and a later upgrade cannot break the metrics
  pipeline on a removed alias.
- The rename changes the collector ConfigMap, so the collector rolls out once at the merge and each
  devops-cli series resets once.
- The change fits one pull request.

## Feasibility

- Read 2026-11-18: `k8s/otel/values.yaml` holds the `deltatocumulative` processor key, its
  comments and the metrics pipeline, and the image `otel/opentelemetry-collector-contrib:0.163.2`
  accepts `delta_to_cumulative`. A local run of that image proved the rename: the deprecation
  warning is gone, and the internal metric name stays `otelcol_deltatocumulative_*` (the processor
  registers its telemetry under the old type), so the dashboard and the documents keep
  `otelcol_deltatocumulative_datapoints`.

## Existing Tool Considered

open-telemetry/opentelemetry-collector-contrib (Apache-2.0, maintained, last activity 2026-11-17)
is already in use, and its `delta_to_cumulative` component type is the current name. The tool keeps
the old `deltatocumulative` name only as a deprecated alias, so the repository must rename its own
key. No new component is built.
