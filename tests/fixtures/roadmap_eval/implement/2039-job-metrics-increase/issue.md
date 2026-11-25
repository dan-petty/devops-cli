## Friction

Each in-cluster Job (`k8s/devops/cronjob.yaml`) is a new pod that exports its metrics once, when it exits. So each Job pod's series holds one sample, and `increase()` or `rate()` over it gives nothing. The AI usage counters of cluster jobs never show in the dashboards.

## Evidence

Found while #1629 was built. #1629 gives roadmap-service one series identity (`service.instance.id=roadmap-service`) and a flush after each batch. A shared instance id does not fix the Jobs, because the CronJobs use `concurrencyPolicy: Allow`, so two Jobs can export to the same series at the same time and the collector drops out-of-order deltas.

## Proposed remedy

- Find the standard answer for short-lived batch jobs in OpenTelemetry: for example, export cumulative totals with a start time, so that Prometheus sees the first sample as an increase from zero, or have the collector's deltatocumulative processor keep the stream across pods.
- Check it against the collector version in `k8s/otel/` before any code change.
- A test shows that two Job runs add up in the query that the dashboards use.
