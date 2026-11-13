# Design

## Decisions

- **Build the metric Resource from the allowed keys only, after merging the SDK detector.**: OTEL_RESOURCE_ATTRIBUTES already wins over the code's values in the merge at the detector call, so a filter over the merged set keeps service.instance.id from the environment and drops every other resource attribute that would split the stream.
- **Keep host.name on the span and log Resource.**: The pod name finds a trace or a log line, and spans and logs do not split a Prometheus series.
- **Set service.instance.id=devops-cli-job in both CronJob templates.**: Each Job pod of the workload then sends the same instance, so its series continues across Job pods instead of starting again at zero, and the new alert fires if a second stream with another resource writes one job and instance.
- **Add the alert to a new rule group metric-streams.**: The otel-collector group pins export-health rules with a 15-minute wait, and this rule waits 30 minutes for another concern; it also watches devops-cli-job, so the roadmap-service group does not fit.
- **Add target_info to SERVED_SERIES.**: The Prometheus OTLP receiver writes target_info from the resource attributes, so the rule selects a series the stack serves, and the served-series check reads that list.
- **Count target_info by job and instance rather than a counter series.**: target_info carries the resource attributes, so two streams of one job and instance give two series before either sends its first counter sample, while a counter may be absent or sparse.
- **Change the document text in the generator and regenerate the reference.**: `docs/TELEMETRY.md` is the output of `src/devops_cli/docs/generator.py`, and the docs row of Static Analysis refuses a generated document that is not the output of its generator; `uv run devops docs generate` writes it.
- **Name only the staged docs command in the plan.**: The rejected plan cited an option that #5198 removed, and `REGENERATE_DOCUMENTS` in `src/devops_cli/roadmap/stage/stage_change.py` is the command that the stage job and `devops ci docs` accept today.
- **List every test module that names a changed manifest in `changes` of the group that changes it.**: The implement job edits only the paths that a group lists, so a manifest change that leaves a referencing test out cannot update that test in the same step.
- **Give the new alert its own group and its own case file, and leave the existing group pins alone.**: The group test compares the whole rule list of a group and the alerts of its case files, so a new alert in an existing group fails those pins.
- **Deliver the live 24-hour check to a person.**: The counts come from the production Prometheus 24 hours after the rollout, which no test of the repository can read.

## Rejected alternatives

- **Keep host.name in the metric Resource and set the instance another way.**: `src/devops_cli/telemetry/tracer.py:1062:"host.name": self.host_name,` gives the collector a new resource at each pod start, and the collector keys a stream by every resource attribute, so the series splits again.
- **Remove host.name from every Resource.**: The span and log Resource of `src/devops_cli/telemetry/tracer.py` keeps the pod name, and a span or a log line does not split a metric series.
- **Use the pod name as service.instance.id.**: The pod name changes at each start, so each start would be a new instance and a new series, which is the defect that #4697 reports.
- **Add the alert to the existing otel-collector group.**: `k8s/monitoring/prometheus-values.yaml:575:- name: otel-collector` holds export-health rules with a 15-minute wait, and the new rule waits 30 minutes for another concern.
- **Count devops_cli_command_total by instance instead of target_info.**: A counter may be absent or sparse, so it does not show a second stream before its first sample, while target_info carries the resource attributes of each stream.
- **Edit `docs/TELEMETRY.md` by hand.**: `docs/TELEMETRY.md` is the output of `src/devops_cli/docs/generator.py`, and the docs row of Static Analysis refuses a generated document that is not the output of its generator.

## Security

Two CronJob templates gain one plain environment variable, OTEL_RESOURCE_ATTRIBUTES=service.instance.id=devops-cli-job, which names a metric stream and carries no secret; the metric Resource that leaves the process loses host.name and keeps only the stable attributes. Nothing else crosses a trust boundary: the Job pods keep a non-root user, a read-only root filesystem, no privilege escalation, all capabilities dropped and the RuntimeDefault seccomp profile. A person confirms that the value holds no secret and that the new rule selects only target_info, which the OTLP receiver writes. `tests/config/test_k8s_devops_runtime.py` fails if a template changes the value or weakens a pod setting, and `tests/prometheus/test_k8s_monitoring_alerting.py` fails if the rule names a series that nothing serves.
