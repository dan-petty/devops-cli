# Design

## Decisions

- **Build the metric Resource from the allowed keys only, after merging the SDK detector.**: OTEL_RESOURCE_ATTRIBUTES already wins over the code's values in the merge at the detector call, so a filter keeps service.instance.id from the environment and drops every other resource attribute that would split the stream.
- **Keep host.name on the span and log Resource.**: The pod name finds a trace or a log line, and spans and logs do not split a Prometheus series.
- **Run one cluster Job of the workload at a time.**: A fixed service.instance.id gives the Job pods one stream, and the OpenTelemetry single-writer rule allows one process per stream. The implement round waits and `devops k8s run-job` refuses while a Job of the workload has not ended, so no two Job pods interleave deltas, which #2039's design rejected.
- **Set service.instance.id=devops-cli-job in both CronJob templates.**: Every Job pod of the workload then sends one instance, so its series continues across Job pods, as the Deployment already does for the Service.
- **Put the alert in a new rule group metric-streams with its own promtool file.**: The rule watches metric stream identity, not collector export health, and it waits 30 minutes where the otel-collector rules wait 15.
- **Count target_info by job and instance for the alert.**: target_info carries the resource attributes of each stream, so two streams of one job and instance show as two series before either sends a counter sample.
- **Rewrite the telemetry reference through `src/devops_cli/docs/generator.py`.**: docs/TELEMETRY.md is a generated document, and the docs check refuses a hand-edited copy.
- **List every test module that reads a changed manifest in the changes of the group that changes it, and give that group one verify path.**: The implement job edits only the files a group lists, so a manifest edit that breaks a reader would stop the step with no file it may fix, and a manifest group's verify takes one path of the group.

## Rejected alternatives

- **Set the fixed instance in both templates without a single-writer guard.**: `k8s/devops/cronjob.yaml:14:concurrencyPolicy: Allow` shows two Jobs may exist at once, and `openspec/changes/archive/2026-10-27-2039-job-metrics-increase/design.md:20:- Force cluster jobs to share a single instance identifier (which causes out-of-order delta drops during concurrent runs).` records that such a stream drops points.
- **Guard concurrency with concurrencyPolicy alone.**: `k8s/devops/cronjob.yaml:13:suspend: true` and the schedule that never fires mean the CronJob creates no Job itself, and `devops k8s run-job` and the Service create the Jobs, so the policy guards nothing and the plan uses a check in the two creators instead.
- **Keep host.name in the metric Resource and set the instance some other way.**: `src/devops_cli/telemetry/tracer.py:1062:"host.name": self.host_name,` gives the collector a new resource at each pod start, and the collector keys a stream by every resource attribute, so the series splits again.
- **Remove host.name from every Resource.**: `src/devops_cli/telemetry/tracer.py:924:{"key": "host.name", "value": {"stringValue": self.host_name}},` keeps the pod name on spans and logs, where it costs no metric series.
- **Give each Job pod its own instance and keep the churn.**: `src/devops_cli/docs/generator.py:1110:"Cluster job pods have unique instance names and export metrics only once when they exit.",` is the state that makes 9 one-sample series for the job in 24 h, which the issue removes.
- **Count devops_cli_command_total by instance for the alert.**: A counter can be absent or sparse, so it shows no second stream before its first sample; target_info exists as soon as a stream sends.
- **Add the alert to the existing otel-collector group.**: `tests/prometheus/test_k8s_monitoring_alerting.py:359:("OtelCollectorExportFailing", "warning"),` pins that group to export-health rules with a 15-minute wait, and the new rule waits 30 minutes for another concern.
- **Verify the template group with every test module that reads the two CronJob templates.**: The verify of a manifest group takes `uv run devops ci test` and one path of the group, so the plan verifies `tests/config/test_k8s_devops_runtime.py` and lists the other readers in the changes of the same group.

## Security

Both CronJob templates gain one environment variable that names the metric instance, and nothing else about the pods changes: they stay non-root, with a read-only root filesystem, no privilege escalation, all capabilities dropped and the RuntimeDefault seccomp profile. A person confirms that service.instance.id=devops-cli-job holds no secret and that the new rule selects only target_info. The runtime test of tests/config/test_k8s_devops_runtime.py fails if a template weakens those pod settings, and the served-series test of tests/prometheus/test_k8s_monitoring_alerting.py fails if the rule names a series that nothing serves.
