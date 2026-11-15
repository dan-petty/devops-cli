# Design: #4528

## Context

`devops-cli` reads `telemetry.endpoint` first and `OTEL_EXPORTER_OTLP_ENDPOINT` only when the
config names no endpoint. The ingest step mounts `devops-cli-config`, which names
`http://otel-collector-opentelemetry-collector.otel.svc.cluster.local:4318`.

## Decisions

- The template drops the variable instead of renaming it: the config already names the endpoint,
  and one source of the address is enough.
- The check reads every `k8s/**/*.yaml` with `yaml.safe_load_all`, finds each environment entry
  named `OTEL_EXPORTER_OTLP_ENDPOINT`, and fails when its host ends with
  `.otel.svc.cluster.local` and is not the Collector Service.
- The unit test points the check at a temporary tree, so it proves the refusal without the
  repository.

## Risks

- A future Service in namespace `otel` that serves OTLP on the standard port is refused. The
  check names the Collector Service, which is the one that answers today, and a person updates
  the constant with the cluster.
