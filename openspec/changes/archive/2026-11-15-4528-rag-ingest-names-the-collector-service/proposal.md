# Proposal: #4528

## Why

WorkflowTemplate rag-ingest set
`OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector.otel.svc.cluster.local:4318`, and namespace
`otel` holds no Service with that name: the Collector chart applies
`otel-collector-opentelemetry-collector`. The step mounts a ConfigMap that already names
`telemetry.endpoint`, so the variable is dead when the config names that endpoint and wrong when
it does not. Closes #4528.

## What Changes

- The WorkflowTemplate drops the `OTEL_EXPORTER_OTLP_ENDPOINT` environment variable, and its
  mounted config names the endpoint.
- A new `k8s` row check, `tests/gate/k8s_checks/otel_endpoints.py`, fails on an
  `OTEL_EXPORTER_OTLP_ENDPOINT` in `k8s/` that names a host in `otel.svc.cluster.local` other
  than the Collector Service, with a unit test of the check in `tests/k8s/`.

## Capabilities

`rag-ingest`: one requirement for the template and the check.

## Impact

One manifest and the `k8s` row. No image, command or gateway change.

## Feasibility

Premise checked on 2026-11-15 against the cluster and `origin/main` (ca62d6a9f): `kubectl -n
otel get svc -o name` lists `otel-collector-opentelemetry-collector`, `tempo` and `tempo-headless`
only, and the ConfigMap names the Collector Service. The check fails on the old value and passes
after the fix.

## Existing Tool Considered

`kubectl kustomize` renders the manifests in the `k8s` row already. No new tool.
