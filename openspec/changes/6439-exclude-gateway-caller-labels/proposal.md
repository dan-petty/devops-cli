# Proposal: #6439

## Why

Issue #6439: since 2026-11-15T23:26Z, Prometheus refuses part of the samples that Alloy sends by remote write. On 2026-11-19, 7,372,993 of 90,762,413 samples failed in 24 h (8.1 %). Each refusal drops a full batch of up to 2,000 samples, so unrelated targets such as `roadmap-service` and `valkey-devops` get gaps.

The cause is the two `labeldrop` rules of the gateway ServiceMonitor that #5896 adds for #4545. LiteLLM writes `client_ip` and `user_agent` on seven metric families. After the drop, two series that differ only in these labels have the same label set and different values at one timestamp. The remote-write receiver answers HTTP 400 "duplicate sample for timestamp", and Alloy drops the batch. Inside one batch, Prometheus also keeps the first sample of a label set and drops the rest with no error, so the stored gateway values are too low.

## What Changes

- `k8s/llm/gateway/config.yaml` sets `prometheus_exclude_labels: ["client_ip", "user_agent"]` under `litellm_settings`, before `callbacks`. LiteLLM then makes each metric without the two labels and adds the counts of all callers into one series before exposition. No two series collide, and the #4545 bound on the series count stays.
- `k8s/llm/gateway/servicemonitor.yaml` loses its comment and its `metricRelabelings` block with the two `labeldrop` rules.
- `tests/gate/k8s_checks/llm_gateway.py` loses `check_the_gateway_endpoint_drops_the_caller_labels` and the constant `SERVICE_MONITOR`. The check asserts values of a manifest (the `labeldrop` list, the port, the path and the interval), which `docs/TESTING.md` forbids, so no check replaces it. The two checks that no dashboard query and no alert expression names the labels stay.
- The change alters a manifest and the series that the gateway serves, which a consumer observes, so it has a spec delta. The delta removes the requirements "The gateway drops the caller address and user agent" and "The manifest check runs in the k8s row", and adds "The gateway excludes the caller address and user agent at the source" and "The label reader checks run in the k8s row". A MODIFIED block must keep each old scenario, and the old scenarios describe the `labeldrop` rules, so the delta removes and adds.

## Capabilities

- Modified: `gateway-caller-telemetry`. Removed: The gateway drops the caller address and user agent; The manifest check runs in the k8s row. Added: The gateway excludes the caller address and user agent at the source; The label reader checks run in the k8s row.

## Impact

- The ConfigMap name of the gateway holds a hash of the config, so the gateway Deployment rolls once after the Argo CD sync of Application `llm`. Its counters start again from 0, which `rate()` and `increase()` handle.
- No panel can split the gateway traffic by caller address or by devops-cli release. No panel, alert rule or command does that now, and the `end_user` label still names each caller.
- The stored gateway history from 2026-11-15T23Z to the rollout stays wrong. This change does not repair it.
- The change fits one pull request.

## Feasibility

Read on 2026-11-19 at tag v1.103.11 of BerriAI/litellm, the image tag of `k8s/llm/gateway/deployment.yaml`:

- `litellm/__init__.py:477-478` declares `prometheus_exclude_metrics` and `prometheus_exclude_labels`.
- `litellm/integrations/prometheus.py:275` reads the setting into the logger, and `:897-919` checks each name against the defined labels. An unknown name raises `ValueError`.
- The metric factory at `:1158-1178` makes each metric without the excluded label names, and `_ExcludedLabelMetric.labels()` (`:163-184`) drops the excluded values. `get_labels_for_metric` (`:1188-1204`) and `_inc_labeled_counter` (`:1304-1317`) are the increment path of all seven families.
- No premium or licence check gates the setting.
- The note at `litellm/proxy/proxy_server.py:5857-5860` says that the order of keys has mattered for other Prometheus settings, so the key comes before `callbacks`.

Measured on 2026-11-19 on the live gateway: `litellm_deployment_total_requests_total{job="llm-gateway"}` holds 323 series, and about 15 remain when the callers add into one series. The raw `/metrics/` page holds 1,502 lines with `client_ip=` or `user_agent=` (138 caller addresses and 40 user agents). Every refused series has `job="llm-gateway"`.

## Existing Tool Considered

LiteLLM's own setting `litellm_settings.prometheus_exclude_labels` covers the need at the source. The change builds no code. It deletes the gate check `check_the_gateway_endpoint_drops_the_caller_labels` and the constant `SERVICE_MONITOR` of `tests/gate/k8s_checks/llm_gateway.py`.

Other options, and why they lose:

- Remove the `labeldrop` rules only: the collisions stop, but the #4545 bound goes, because the TTL never removes the deployment series.
- `prometheus_metrics_config` with `include_labels`: it is include-based, so each family that is not listed stops.
- Upgrade LiteLLM for `prometheus_metrics_max_series_per_metric`: not in v1.103.11, and the labels stay.
- Aggregate in Alloy or in the OpenTelemetry Collector: correct, but 40 to 60 lines of custom glue for one target.
- Relabel the two labels to a constant: a relabel rule cannot add values, so the collisions stay.
- Scrape the gateway directly with Prometheus: the TSDB keeps the first sample of each label set with no signal.
- Alloy remote write 2.0: only the samples of other targets stay.
- `use_x_forwarded_for` and a user agent with no release: each caller must comply, and the header can get around the rate limit by source.
