# Design

## Decisions
- Keep `LogPane` and `VirtualLogBuffer` in `devops_cli.ui` because `TelemetryPanel` uses them to stream Loki logs.
- Remove `PodInspector`, `K8sPanel`, and Kubernetes data providers (`fetch_k8s_status`, `fetch_pod_events`) from `devops_cli.ui`.
- Remove the Kubernetes summary panel from `devops dashboard --summary`.
- Change default tab from `k8s` to `docker`.
- Map numeric tab shortcuts 1, 2, and 3 to Docker, Telemetry, and Valkey respectively.

## Rejected alternatives
- Keep `K8sPanel` as a disabled tab: Rejected because the project avoids inactive or zombie code before version 1.0.0.
- Retain pod log streaming under `LogPane`: Rejected because k9s provides superior live pod log inspection.
