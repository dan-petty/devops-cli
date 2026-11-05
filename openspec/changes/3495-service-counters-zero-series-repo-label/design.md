# Design

## Decisions

- **The Service creates the bounded label sets of its counters at zero when it starts.** A labelled counter has no series until `.labels()` makes a child (see the Feasibility of the proposal). One function calls `.labels()` for each bounded label set, so the first scrape of a pod reads a zero series for each label set.
- **The label sets are bounded.** The failure classes are the 19 members of `FailureClass`. The repositories are `service.repos`. The rows are the rows of the three lane tables of the roadmap run. The events of the webhook counter are the declared events of each provider, plus `other`. No dynamic label value is created at start.
- **The exposition format stays text 0.0.4.** The Service serves `/metrics` in this format (`src/devops_cli/server/service.py`). The zero children appear in this format, so the change does not switch the format.
- **The jobs counter counts each row.** The roadmap run counts each row of a lane with its result, with the row name of the row table. The worker counts the scoped updates with the name of their job. A row counted in the run is not counted again in the worker, so no job is counted twice.
- **The OTLP workaround terms stay.** The GitHub request and AI request series reach Prometheus over OTLP, not the `/metrics` scrape. The comment at `k8s/monitoring/prometheus-values.yaml` says that an OTLP series gets a sample only when the Service sends a new observation. No live Prometheus query ran in this change, so the OTLP terms stay until a live check shows that they are not needed.
- **The gap of a new pod stays.** The zero children are created at start. A count made before the first scrape of a new pod is still lost, because `increase()` does not count the first sample of a series. The documents state this gap.
- **No recording rule.** The promtool case of a pod change decides whether a recording rule is needed. The case runs with the zero series of the new pod.

## Rejected alternatives

- **Switch `/metrics` to OpenMetrics or PrometheusProto for start timestamps.** Rejected: the change of format reaches every consumer of `/metrics`, and the start-timestamp injection is not verified for this path. The zero children solve the missing first sample without a format change.
- **Keep the per-batch count and add a second count per row.** Rejected: one job would be counted twice, once per lane batch and once per row.
- **Prime the identity label of `devops_cli_service_identity_refused_total`.** Rejected for this change: the identity values come from the configured GitHub App, the alert `RoadmapServiceIdentityRefused` reads `> 0` with no workaround term, and the label set is not in the acceptance criteria of the issue. It stays an open item.
- **Add a recording rule for the true total without a test.** Rejected: a recording rule adds a second series name for one counter. It needs a promtool case that shows the need first.
