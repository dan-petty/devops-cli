# Design

## Decisions

- **The Service creates the bounded label sets of its counters at zero when it starts.** A labelled counter has no series until `.labels()` makes a child (see the Feasibility of the proposal). One function calls `.labels()` for each bounded label set, so the first scrape of a pod reads a zero series for each label set.
- **The label sets are bounded.** The failure classes are the 19 members of `FailureClass`. The repositories are `service.repos`. The rows are the rows of the three lane tables of the roadmap run. The events of the webhook counter are the declared events of each provider, plus `other`. The results of the job counter are `success`, `error` and `stopped`. The sources of the trigger counter are `webhook` and `poll`. The results of the chat command are `usage`, `status`, `unknown_repo` and `error`. No dynamic label value is created at start.
- **The exposition format stays text 0.0.4.** The Service serves `/metrics` in this format (`src/devops_cli/server/service.py`). The zero children appear in this format, so the change does not switch the format.
- **The jobs counter counts each row.** The roadmap run counts each row of a lane with its result, with the row name of the row table. The worker counts the scoped updates with the name of their job. A row counted in the run is not counted again in the worker, so no job is counted twice.
- **A stop is no failed row.** A row or a scoped update that the stop of the Service ends counts under `result="stopped"`. `RoadmapServiceJobsFailing` reads only `error` and `success`, so a rollout does not fire it for a row that runs twice a day.
- **`RoadmapServiceJobsFailing` reads the row.** The rule groups and joins on `repo`, `lane` and `row`. Before this change, a failed row made its whole round an error. With a count for each row, the row `metrics` succeeds in each status-lane round, so a join on the lane never fires for a failed row of that lane. A promtool case holds this.
- **The Loki query of `RoadmapServiceJobsFailing` has no field `row`.** The log line of a failed round has no such field, and its text names the rows. The summary of the alert names the row.
- **The budget hold counter is primed too.** It has no label, but the registry creates a counter at its first count, so it has no series before the first hold.
- **The OTLP workaround terms stay.** The GitHub request and AI request series reach Prometheus over OTLP, not the `/metrics` scrape. The comment at `k8s/monitoring/prometheus-values.yaml` says that an OTLP series gets a sample only when the Service sends a new observation. No live Prometheus query ran in this change, so the OTLP terms stay until a live check shows that they are not needed.
- **The gap of a new pod stays.** The zero children are created at start. A count made before the first scrape of a new pod is still lost, because `increase()` does not count the first sample of a series. The documents state this gap.
- **No recording rule.** The promtool case of a pod change decides whether a recording rule is needed. The case runs with the zero series of the new pod.

## Rejected alternatives

- **Switch `/metrics` to OpenMetrics or PrometheusProto for start timestamps.** Rejected: the change of format reaches every consumer of `/metrics`, and the start-timestamp injection is not verified for this path. The zero children solve the missing first sample without a format change.
- **Keep the per-batch count and add a second count per row.** Rejected: one job would be counted twice, once per lane batch and once per row.
- **Prime the identity label of `devops_cli_service_identity_refused_total`.** Rejected: its label `identity` holds the identity that GitHub refuses, so its value is not known before a refusal. The alert `RoadmapServiceIdentityRefused` reads `> 0` with no workaround term, so the alert does not need a zero series.
- **Add the field `row` to the Loki query of `RoadmapServiceJobsFailing`.** Rejected: the log line has no field `row`, so the query would give no line.
- **Keep the join of `RoadmapServiceJobsFailing` on the lane.** Rejected: the promtool case of a row that fails each round, while the row `metrics` of its lane succeeds, gives no alert with this join.
- **Count a round that fails before its first row in this change.** Rejected: the failure of a round has no row, so it needs its own label value or counter and its own alert. #3666 holds this work.
- **Add a recording rule for the true total without a test.** Rejected: a recording rule adds a second series name for one counter. It needs a promtool case that shows the need first.
