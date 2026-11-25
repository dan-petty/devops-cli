"""The alert rules of the Prometheus server: promtool checks them and runs their unit tests.

The environment rules live in `k8s/monitoring/prometheus-values.yaml`
(`serverFiles.alerting_rules.yml`). The product rules, which watch the `devops_cli_` series, live
in `k8s/devops/monitoring/prometheus-rules-values.yaml`
(`serverFiles.devops_cli_alerting_rules.yml`), the second values file of the chart (#5292). The
server loads each file that `rule_files` of the environment values names. A rule over a series
nothing in the stack serves never fires, so every expression may name only the series in
`SERVED_SERIES`, each served by a scrape or by the OpenTelemetry collector that this repository
defines. The k3s server runs the controller manager, scheduler and proxy in its own process, so
no scrape targets them and none of their series is listed: a rule over them would fire on the
missing target, as `KubeControllerManagerDown`, `KubeSchedulerDown` and `KubeProxyDown` did.

The checks read files only, except the two that run promtool: `promtool check rules` over every
rule, and `promtool test rules` over each group that has unit tests in
`tests/fixtures/prometheus_rules/`. Each skips where promtool is not installed. They run the
promtool of the devtools image, which the devcontainer has and which CI copies with
`.github/actions/devtools-commands` and puts on PATH.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

import pytest
import yaml
from markdown_it import MarkdownIt
from markdown_it.tree import SyntaxTreeNode

from devops_cli.config.constants import (
    CONST_GH_MUTATION_HTTP_METHODS,
    CONST_SERVICE_METRIC_BUDGET_LIMIT,
    CONST_SERVICE_METRIC_BUDGET_SPENT,
    CONST_SERVICE_METRIC_FIX_CHECKS_JOBS,
    CONST_SERVICE_METRIC_IDENTITY_REFUSED,
    CONST_SERVICE_METRIC_IMPLEMENT_FAILURES,
    CONST_SERVICE_METRIC_JOB_RETRY_AFTER_SECONDS,
    CONST_SERVICE_METRIC_JOB_START_TIMESTAMP,
    CONST_SERVICE_METRIC_JOB_SUSPENDED,
    CONST_SERVICE_METRIC_JOBS,
    CONST_SERVICE_METRIC_STAGE_JOBS,
    CONST_SERVICE_METRIC_WEBHOOK_DELIVERIES,
    CONST_SERVICE_METRIC_WEBHOOK_DELIVERY_FAILURES,
)
from devops_cli.exceptions import ConfigurationError
from devops_cli.prometheus.client import parse_duration
from devops_cli.prometheus.promql import selectors
from devops_cli.prometheus.slo_rules import SLO_RECORD_NAMES
from devops_cli.telemetry import instruments as _instruments
from devops_cli.telemetry.instruments import (
    AI_REQUESTS_TOTAL,
    AI_SPEND_USD_TOTAL,
    CRAWL4AI_FETCHES_TOTAL,
    GITHUB_REQUESTS_TOTAL,
    GITHUB_THROTTLE_WAIT,
    RAG_INGEST_LAST_SUCCESS_TIMESTAMP,
    RESEARCH_OPEN_FINDINGS,
    ROADMAP_ALTERNATIVES_UNCHECKED_ITEMS,
    ROADMAP_ITEM_AGE,
    ROADMAP_OLDEST_ITEM,
    ROADMAP_TOOL_CALLS_PER_RUN,
    ROADMAP_TOOL_CALLS_TOTAL,
    WEB_SEARCHES_TOTAL,
)
from tests.support.paths import FIXTURES, REPO_ROOT
from tests.support.promtool import promtool

if TYPE_CHECKING:
    from devops_cli.prometheus.slo_rules import SloSpec

K8S = REPO_ROOT / "k8s"
K8S_README = K8S / "README.md"
CLUSTER_DOC = REPO_ROOT / "docs" / "CLUSTER.md"
PROMETHEUS_VALUES = K8S / "monitoring" / "prometheus-values.yaml"
PRODUCT_RULES_VALUES = K8S / "devops" / "monitoring" / "prometheus-rules-values.yaml"
ROADMAP_SERVICE_RULE_TESTS = FIXTURES / "prometheus_rules" / "roadmap_service_tests.yaml"
ROADMAP_SERVICE_RECORDING_RULE_TESTS = (
    FIXTURES / "prometheus_rules" / "roadmap_service_recording_tests.yaml"
)
ROADMAP_SERVICE_WEBHOOKS_RULE_TESTS = (
    FIXTURES / "prometheus_rules" / "roadmap_service_webhooks_tests.yaml"
)
ROADMAP_SERVICE_ACTIVITY_RULE_TESTS = (
    FIXTURES / "prometheus_rules" / "roadmap_service_activity_tests.yaml"
)
ROADMAP_SERVICE_ACTIVITY_HOURLY_RULE_TESTS = (
    FIXTURES / "prometheus_rules" / "roadmap_service_activity_hourly_tests.yaml"
)
ROADMAP_SERVICE_ITEMS_RULE_TESTS = (
    FIXTURES / "prometheus_rules" / "roadmap_service_items_tests.yaml"
)
ROADMAP_SERVICE_TOOLS_RULE_TESTS = (
    FIXTURES / "prometheus_rules" / "roadmap_service_tools_tests.yaml"
)
CRAWL4AI_RULE_TESTS = FIXTURES / "prometheus_rules" / "crawl4ai_tests.yaml"
OTEL_COLLECTOR_RULE_TESTS = FIXTURES / "prometheus_rules" / "otel_collector_tests.yaml"
VALKEY_MEMORY_RULE_TESTS = FIXTURES / "prometheus_rules" / "valkey_memory_tests.yaml"
RESEARCH_RULE_TESTS = FIXTURES / "prometheus_rules" / "research_tests.yaml"
REPOS_DRIFT_RULE_TESTS = FIXTURES / "prometheus_rules" / "repos_drift_tests.yaml"
AI_SPEND_RULE_TESTS = FIXTURES / "prometheus_rules" / "ai_spend_tests.yaml"
GATEWAY_DATABASE_RULE_TESTS = FIXTURES / "prometheus_rules" / "llm_gateway_db_tests.yaml"
METRIC_STREAMS_RULE_TESTS = FIXTURES / "prometheus_rules" / "metric_streams_tests.yaml"
# The SLO groups of #4709: the render of the Sloth specs of k8s/devops/monitoring/slos/, one case
# file for each.
SLO_ROADMAP_SERVICE_ROUNDS_RULE_TESTS = (
    FIXTURES / "prometheus_rules" / "slo_roadmap_service_rounds_tests.yaml"
)
SLO_RUNNER_JOBS_DURATION_RULE_TESTS = (
    FIXTURES / "prometheus_rules" / "slo_runner_jobs_duration_tests.yaml"
)
SLO_LLM_GATEWAY_REQUESTS_RULE_TESTS = (
    FIXTURES / "prometheus_rules" / "slo_llm_gateway_requests_tests.yaml"
)
SLO_LLM_GATEWAY_LATENCY_RULE_TESTS = (
    FIXTURES / "prometheus_rules" / "slo_llm_gateway_latency_tests.yaml"
)

ROADMAP_SERVICE_GROUP = "roadmap-service"
# The row work series that the group records for its alerts, the dashboards and the start page
# (#4562).
ROADMAP_SERVICE_RECORDING_GROUP = "roadmap-service-recording"
# The group of the Service's webhook route, apart from the Service's group (#2476).
ROADMAP_SERVICE_WEBHOOKS_GROUP = "roadmap-service-webhooks"
# The Service's writes, the deliveries of its own writes and its web search (#2475).
ROADMAP_SERVICE_ACTIVITY_GROUP = "roadmap-service-activity"
# The age of the oldest roadmap item in each state, and its alert (#2919).
ROADMAP_SERVICE_ITEMS_GROUP = "roadmap-service-items"
# The tools of the stage planner that no run called (#3240).
ROADMAP_SERVICE_TOOLS_GROUP = "roadmap-service-tools"
# Each group of the roadmap Service, with a file of promtool unit tests of its rules. A group
# whose cases need two evaluation intervals has one file for each interval.
ROADMAP_SERVICE_GROUP_TESTS = (
    (ROADMAP_SERVICE_GROUP, ROADMAP_SERVICE_RULE_TESTS),
    (ROADMAP_SERVICE_RECORDING_GROUP, ROADMAP_SERVICE_RECORDING_RULE_TESTS),
    (ROADMAP_SERVICE_WEBHOOKS_GROUP, ROADMAP_SERVICE_WEBHOOKS_RULE_TESTS),
    (ROADMAP_SERVICE_ACTIVITY_GROUP, ROADMAP_SERVICE_ACTIVITY_RULE_TESTS),
    (ROADMAP_SERVICE_ACTIVITY_GROUP, ROADMAP_SERVICE_ACTIVITY_HOURLY_RULE_TESTS),
    (ROADMAP_SERVICE_ITEMS_GROUP, ROADMAP_SERVICE_ITEMS_RULE_TESTS),
    (ROADMAP_SERVICE_TOOLS_GROUP, ROADMAP_SERVICE_TOOLS_RULE_TESTS),
)
# The page fetches of the Crawl4AI service and its Deployment (#3893).
CRAWL4AI_GROUP = "crawl4ai"
# The rules over the OpenTelemetry collector's own telemetry (#1642).
OTEL_COLLECTOR_GROUP = "otel-collector"
# The rule of a Valkey that refuses writes at its memory bound (#2094).
VALKEY_MEMORY_GROUP = "valkey-memory"
# The rule over the open findings of `devops research sweep` (#3899).
RESEARCH_GROUP = "research"
# The rules over the nightly drift check of the repository settings (#6783).
REPOS_DRIFT_GROUP = "repos-drift"
# The rules over the daily USD spend of the hosted models (#4222).
AI_SPEND_GROUP = "ai-spend"
# The rule of two metric streams that write one Prometheus series (#4697).
METRIC_STREAMS_GROUP = "metric-streams"
# The rules of the database of the LLM gateway, a CloudNativePG Cluster of one instance (#4994).
GATEWAY_DATABASE_GROUP = "llm-gateway-db"
# The four SLO groups of #4709, one for each Sloth spec of k8s/devops/monitoring/slos/: the row
# runs of the roadmap Service, the duration of its runner Jobs and the requests and the latency of
# the LLM gateway.
SLO_ROADMAP_SERVICE_ROUNDS_GROUP = "slo-roadmap-service-rounds"
SLO_RUNNER_JOBS_DURATION_GROUP = "slo-runner-jobs-duration"
SLO_LLM_GATEWAY_REQUESTS_GROUP = "slo-llm-gateway-requests"
SLO_LLM_GATEWAY_LATENCY_GROUP = "slo-llm-gateway-latency"
# Each group whose rules have promtool unit tests, with a file of its tests.
RULE_GROUP_TESTS = (
    *ROADMAP_SERVICE_GROUP_TESTS,
    (CRAWL4AI_GROUP, CRAWL4AI_RULE_TESTS),
    (OTEL_COLLECTOR_GROUP, OTEL_COLLECTOR_RULE_TESTS),
    (VALKEY_MEMORY_GROUP, VALKEY_MEMORY_RULE_TESTS),
    (RESEARCH_GROUP, RESEARCH_RULE_TESTS),
    (REPOS_DRIFT_GROUP, REPOS_DRIFT_RULE_TESTS),
    (AI_SPEND_GROUP, AI_SPEND_RULE_TESTS),
    (GATEWAY_DATABASE_GROUP, GATEWAY_DATABASE_RULE_TESTS),
    (METRIC_STREAMS_GROUP, METRIC_STREAMS_RULE_TESTS),
    (SLO_ROADMAP_SERVICE_ROUNDS_GROUP, SLO_ROADMAP_SERVICE_ROUNDS_RULE_TESTS),
    (SLO_RUNNER_JOBS_DURATION_GROUP, SLO_RUNNER_JOBS_DURATION_RULE_TESTS),
    (SLO_LLM_GATEWAY_REQUESTS_GROUP, SLO_LLM_GATEWAY_REQUESTS_RULE_TESTS),
    (SLO_LLM_GATEWAY_LATENCY_GROUP, SLO_LLM_GATEWAY_LATENCY_RULE_TESTS),
)
RULE_TEST_IDS = [rule_tests.stem for _, rule_tests in RULE_GROUP_TESTS]
# promtool evaluates the rules of a group once each `evaluation_interval` of a file, from 0 to
# the last `eval_time` of a case. A case of 150 hours at 1 minute made 9,000 rounds of a group
# of 4 rules and took 64 s on a CI runner (#4456). The longest case of the other files makes 390.
MAX_PROMTOOL_ROUNDS = 1_000

# The job matcher of each rule of the recording group: the Service's own job, and the job of a row
# pod, which is named after the pod (#4562).
ROADMAP_SERVICE_RECORDING_JOB_MATCHER = 'job=~"roadmap-service|roadmap-.+"'
# The row work selectors that the recording group shares (#4562): the metrics that each selector
# reads, and the record name of its rule. A single-metric selector's record name holds its metric;
# the budget ratio's holds `_per_` and `ratio`.
COVERED_ROW_WORK_SELECTORS = (
    ((CONST_SERVICE_METRIC_JOBS,), "repo_lane_row:devops_cli_service_jobs_total:increase1h"),
    (
        (CONST_SERVICE_METRIC_BUDGET_SPENT, CONST_SERVICE_METRIC_BUDGET_LIMIT),
        "service:devops_cli_service_budget_requests_per_limit:ratio",
    ),
    (
        (CONST_SERVICE_METRIC_JOB_SUSPENDED,),
        "repo_row_class:devops_cli_service_job_suspended:max",
    ),
)
# The record names of the row work series: each is a series that the server serves, because the
# group records it.
RECORDED_ROW_WORK_SERIES = tuple(record for _, record in COVERED_ROW_WORK_SELECTORS)
# The row work alerts that read a recorded series of `roadmap-service-recording` (#4562): the
# failed jobs of a row, the GitHub request budget of the Service and the rows that stay suspended.
# The router health alerts keep their raw `job="roadmap-service"` selector, because the router
# keeps the job.
ROW_WORK_ALERTS = (
    "RoadmapServiceJobsFailing",
    "RoadmapServiceGitHubRequestsHigh",
    "RoadmapServiceRowSuspended",
)

# Every series an alert rule may select, by what serves it.
SERVED_SERIES = frozenset(
    {
        # Recorded by Prometheus for every scrape.
        "up",
        # kube-state-metrics, deployed and scraped by k8s-monitoring.
        "kube_node_status_condition",
        "kube_persistentvolumeclaim_info",
        "kube_persistentvolumeclaim_resource_requests_storage_bytes",
        "kube_pod_info",
        "kube_pod_spec_volumes_persistentvolumeclaims_info",
        "kube_secret_info",
        # The roadmap Service's restarts and replicas (#2472).
        "kube_deployment_spec_replicas",
        "kube_deployment_status_replicas_available",
        "kube_deployment_status_replicas_unavailable",
        "kube_pod_container_status_restarts_total",
        # The memory limit and the working set of the roadmap Service's container (#4116).
        "kube_pod_container_resource_limits",
        "container_memory_working_set_bytes",
        # Not in the chart's default allow list: `metricsTuning.includeMetrics` keeps it (#1817).
        "kube_ingress_path",
        # The kubelet, scraped by k8s-monitoring (its default allow list), reports these only for
        # volumes whose plugin measures them. No claim on this cluster does (local-path volumes
        # are host directories), so the rule over them stays silent until one does.
        "kubelet_volume_stats_available_bytes",
        "kubelet_volume_stats_capacity_bytes",
        # node-exporter, scraped by k8s-monitoring's host metrics with no allow list (#1129);
        # systemd unit state comes from the collector #1080 turned on.
        "node_boot_time_seconds",
        "node_filesystem_avail_bytes",
        "node_filesystem_size_bytes",
        "node_systemd_unit_state",
        "node_time_seconds",
        # The DCGM exporter on every GPU node, through k8s-monitoring's dcgm-exporter integration.
        "DCGM_FI_DEV_GPU_TEMP",
        "DCGM_FI_DEV_POWER_USAGE",
        # The Prometheus server's self-scrape (`scrapeConfigs.prometheus`).
        "prometheus_config_last_reload_successful",
        "prometheus_notifications_alertmanagers_discovered",
        "prometheus_notifications_dropped_total",
        "prometheus_rule_evaluation_failures_total",
        "prometheus_tsdb_compactions_failed_total",
        "prometheus_tsdb_head_chunks_storage_size_bytes",
        "prometheus_tsdb_retention_limit_bytes",
        "prometheus_tsdb_size_retentions_total",
        "prometheus_tsdb_storage_blocks_bytes",
        "prometheus_tsdb_wal_storage_size_bytes",
        # Alloy collectors, scraped by k8s-monitoring's Alloy integration within its default allow
        # list (#1131).
        "loki_write_dropped_entries_total",
        "loki_write_sent_entries_total",
        "prometheus_remote_storage_samples_failed_total",
        # Loki, scraped by k8s-monitoring's Loki integration within its default allow list, which
        # finds Loki's pods only where the logging stack runs.
        "loki_compactor_apply_retention_last_successful_run_timestamp_seconds",
        "loki_request_duration_seconds_count",
        # The OpenTelemetry collector's own telemetry, scraped by the server's kubernetes-pods
        # job (#1642). Each send_failed counter starts at the first send that fails.
        "otelcol_exporter_queue_capacity",
        "otelcol_exporter_queue_size",
        "otelcol_exporter_send_failed_log_records",
        "otelcol_exporter_send_failed_metric_points",
        "otelcol_exporter_send_failed_spans",
        # Pyroscope, scraped through its ServiceMonitor (#1131, #1134).
        "pyroscope_request_duration_seconds_count",
        # Alertmanager, found through its pod annotations by k8s-monitoring's annotation
        # autodiscovery.
        "alertmanager_config_last_reload_successful",
        "alertmanager_notifications_failed_total",
        # The CloudNativePG metrics exporter of each instance, through the PodMonitors
        # `mattermost-db` (#1391) and `llm-gateway-db` (#4994).
        "cnpg_backends_total",
        "cnpg_collector_pg_wal",
        "cnpg_collector_up",
        "cnpg_pg_database_size_bytes",
        "cnpg_pg_settings_setting",
        # SeaweedFS, through the ServiceMonitors that its operator makes from the Seaweed CR of
        # namespace object-store (#4750).
        "SeaweedFS_master_is_leader",
        "SeaweedFS_master_under_replicated_volumes",
        "SeaweedFS_volumeServer_read_only_volumes",
        "SeaweedFS_volumeServer_resource",
        # Argo CD, cloudflared, CoreDNS (#822), and Valkey redis_exporter (#551, #2094).
        "argocd_app_info",
        "cloudflared_tunnel_ha_connections",
        "coredns_dns_responses_total",
        "redis_instance_info",
        "redis_memory_max_bytes",
        "redis_memory_used_bytes",
        "redis_rejected_connections_total",
        "redis_up",
        # The roadmap Service (#2472): the series of its /metrics, which k8s-monitoring's
        # annotation autodiscovery scrapes, and the instruments it sends over OTLP. A histogram
        # is a native histogram under the instrument's own name.
        CONST_SERVICE_METRIC_BUDGET_LIMIT,
        CONST_SERVICE_METRIC_BUDGET_SPENT,
        CONST_SERVICE_METRIC_IDENTITY_REFUSED,
        CONST_SERVICE_METRIC_JOBS,
        CONST_SERVICE_METRIC_JOB_START_TIMESTAMP,
        # The fix-checks Jobs that the watch row starts and reports (#5027).
        CONST_SERVICE_METRIC_FIX_CHECKS_JOBS,
        # The stage Jobs that the stage row reports and the implement failures by class (#6821).
        CONST_SERVICE_METRIC_STAGE_JOBS,
        CONST_SERVICE_METRIC_IMPLEMENT_FAILURES,
        # The suspended rows and the seconds before each runs again (#4065).
        CONST_SERVICE_METRIC_JOB_SUSPENDED,
        CONST_SERVICE_METRIC_JOB_RETRY_AFTER_SECONDS,
        "devops_cli_service_state_unkept",
        CONST_SERVICE_METRIC_WEBHOOK_DELIVERIES,
        # GitHub's record of the failed deliveries of the hooks, set by the metrics row (#5017).
        CONST_SERVICE_METRIC_WEBHOOK_DELIVERY_FAILURES,
        AI_REQUESTS_TOTAL.name,
        # The USD spend of the model calls, priced by the model that the client asked for (#4222).
        AI_SPEND_USD_TOTAL.name,
        # The page fetches of the Service through Crawl4AI (#3893).
        CRAWL4AI_FETCHES_TOTAL.name,
        WEB_SEARCHES_TOTAL.name,
        GITHUB_REQUESTS_TOTAL.name,
        GITHUB_THROTTLE_WAIT.name,
        # The age of each roadmap phase and its number, and counts (#2919, #5495).
        ROADMAP_ITEM_AGE.name,
        *(
            [getattr(_instruments, "ROADMAP_ITEMS").name]
            if hasattr(_instruments, "ROADMAP_ITEMS")
            else []
        ),
        ROADMAP_OLDEST_ITEM.name,
        *(
            [getattr(_instruments, "ROADMAP_STALLED_ITEMS").name]
            if hasattr(_instruments, "ROADMAP_STALLED_ITEMS")
            else []
        ),
        # The open findings of the research sweep, by severity (#3899).
        RESEARCH_OPEN_FINDINGS.name,
        # The rows of the nightly drift check of each repository, by state (#6783).
        *(
            [getattr(_instruments, "REPOS_DRIFT_ROWS").name]
            if hasattr(_instruments, "REPOS_DRIFT_ROWS")
            else []
        ),
        # The items that the alternatives check has not checked, sent by its row (#2950).
        ROADMAP_ALTERNATIVES_UNCHECKED_ITEMS.name,
        # The calls of the stage planner's tools, and its plan runs (#3240).
        ROADMAP_TOOL_CALLS_PER_RUN.name,
        ROADMAP_TOOL_CALLS_TOTAL.name,
        # Freshness of the in-cluster RAG ingest runs (#1653).
        RAG_INGEST_LAST_SUCCESS_TIMESTAMP.name,
        # The recorded row work series of the roadmap Service (#4562): the failed jobs of the
        # last hour, the budget used ratio and the suspended rows.
        *RECORDED_ROW_WORK_SERIES,
        # The five series of the four SLO groups of #4709: the start and the end of each runner Job
        # of the runner image, and the requests and the latency of the LLM gateway.
        "kube_job_status_start_time",
        "kube_job_status_completion_time",
        "litellm_proxy_total_requests_metric_total",
        "litellm_proxy_failed_requests_metric_total",
        "litellm_request_total_latency_metric_bucket",
        # The series that the four SLO groups record, one group for each Sloth spec (#4709).
        *SLO_RECORD_NAMES,
        # The resource attributes of each stream that the OTLP receiver of Prometheus writes, one
        # series for each stream of a job and instance (#4697).
        "target_info",
    }
)


@cache
def _yaml(path: Path) -> dict[str, Any]:
    """A values file, read once; the tests only read it."""
    loaded: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded


def _server_files() -> dict[str, Any]:
    """The `serverFiles` of the chart: the environment values, then the product values."""
    return {
        **_yaml(PROMETHEUS_VALUES)["serverFiles"],
        **_yaml(PRODUCT_RULES_VALUES)["serverFiles"],
    }


def _rule_files() -> dict[str, dict[str, Any]]:
    """Each rule file that the server loads and that holds groups, by its key of `serverFiles`."""
    server_files = _server_files()
    keys = [PurePosixPath(path).name for path in server_files["prometheus.yml"]["rule_files"]]
    return {key: server_files[key] for key in keys if (server_files.get(key) or {}).get("groups")}


def _groups() -> list[dict[str, Any]]:
    """Every rule group that the server loads, in the order of `rule_files`."""
    return [group for rules in _rule_files().values() for group in rules["groups"]]


def _rules() -> list[dict[str, Any]]:
    """Every rule the Prometheus server loads."""
    return [rule for group in _groups() for rule in group["rules"]]


def _group(name: str) -> list[dict[str, Any]]:
    """The rules of one group, in file order."""
    (rules,) = [group["rules"] for group in _groups() if group["name"] == name]
    return list(rules)


def _unserved(expression: str) -> list[str]:
    """Each selector in an expression that names no metric or one nothing serves."""
    return [
        f"{expression}: {selector.metric}"
        for selector in selectors(expression)
        if selector.metric not in SERVED_SERIES
    ]


@pytest.mark.parametrize(
    ("expression", "unserved"),
    [
        ("up == 0", 0),
        ('absent(kube_scheduler_schedule_attempts_total{job="kube-scheduler"})', 1),
        ('{__name__=~"node_.+"} > 0', 1),
    ],
    ids=["served", "k3s-component", "no-metric-name"],
)
def test_the_served_series_check_rejects_what_nothing_serves(
    expression: str, unserved: int
) -> None:
    """Pin the check on literal expressions: an unknown series, and a selector with no name."""
    assert len(_unserved(expression)) == unserved


# One part of a record name, which is the `level:metric:operations` form of the Prometheus naming
# practice (#4562), and the `by (...)` grouping of an expression.
_RECORD_NAME_PART = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*")
_GROUPING_LABELS = re.compile(r"by \(([^)]*)\)")


def test_every_alert_rule_selects_only_series_the_stack_serves() -> None:
    """A rule over a series no scrape serves stays silent, or fires on the missing target.

    The recording rules of `roadmap-service-recording` (#4562) are part of the check: each has a
    `level:metric:operations` name, each covered row work selector has one rule and no other, each
    rule matches the Service's own job and the job of a row pod, and each record name is served.
    Each row work alert then reads a recorded series of that group, and holds no raw
    `job="roadmap-service"` selector, so the move of the row work into `roadmap-<row>` pods changes
    the job of its series and no alert. The check sits here, in a test that already reads the rule
    file: the `test-tree` row holds this module to a count of tests that read a config file, and
    the count only falls (#6060).
    """
    rules = _rules()
    assert (len(rules) > 0, [v for rule in rules for v in _unserved(rule["expr"])]) == (True, [])
    recording = _group(ROADMAP_SERVICE_RECORDING_GROUP)

    def selected(rule: dict[str, Any]) -> list[str | None]:
        return sorted(selector.metric for selector in selectors(rule["expr"]))

    # A record name has exactly two colons, and each of its three parts is an identifier.
    assert [
        record
        for record in (str(rule.get("record", "")) for rule in recording)
        if len(record.split(":")) != 3
        or not all(_RECORD_NAME_PART.fullmatch(part) for part in record.split(":"))
    ] == []
    # One rule for each covered selector, and no fourth rule, each selecting only the metrics of
    # its selector and recording them under the name that the selector names.
    assert len(recording) == len(COVERED_ROW_WORK_SELECTORS)
    assert {
        record: [
            (rule.get("record"), selected(rule))
            for rule in recording
            if set(metrics) & set(selected(rule))
        ]
        for metrics, record in COVERED_ROW_WORK_SELECTORS
    } == {record: [(record, sorted(metrics))] for metrics, record in COVERED_ROW_WORK_SELECTORS}
    assert [
        record
        for metrics, record in COVERED_ROW_WORK_SELECTORS
        if not (
            all(metric in record for metric in metrics)
            if len(metrics) == 1
            else all(part in record for part in ("_per_", "ratio"))
        )
    ] == []
    # Each rule matches the Service's job and the row pods' jobs, and records a served name.
    assert [
        rule.get("record")
        for rule in recording
        if ROADMAP_SERVICE_RECORDING_JOB_MATCHER not in rule["expr"]
        or rule.get("record") not in SERVED_SERIES
    ] == []
    # The failed jobs rule keeps the `result` label, so the alert compares the error series with
    # the success series of one repo, lane and row.
    (jobs,) = [rule for rule in recording if rule.get("record") == RECORDED_ROW_WORK_SERIES[0]]
    assert [
        sorted(grouping.split(", ")) for grouping in _GROUPING_LABELS.findall(jobs["expr"])
    ] == [["lane", "repo", "result", "row"]]
    # Each row work alert reads a recorded series of the group, and no raw selector of the
    # Service's own job (#4562).
    row_work = [
        rule for rule in _group(ROADMAP_SERVICE_GROUP) if rule.get("alert") in ROW_WORK_ALERTS
    ]
    recorded = {str(rule["record"]) for rule in recording}
    assert sorted(str(rule["alert"]) for rule in row_work) == sorted(ROW_WORK_ALERTS)
    # Each selector of an expression names a series that a rule of the recording group records.
    assert [
        (rule["alert"], selector.metric)
        for rule in row_work
        for selector in selectors(rule["expr"])
        if selector.metric not in recorded
    ] == []
    # Each alert reads at least one recorded series.
    assert [
        rule["alert"]
        for rule in row_work
        if not any(selector.metric in recorded for selector in selectors(rule["expr"]))
    ] == []
    assert [rule["alert"] for rule in row_work if 'job="roadmap-service"' in rule["expr"]] == []


# The regular expression of a `method=~` matcher.
_METHOD_REGEX_MATCHER = re.compile(r'method=~"([^"]*)"')


def test_the_write_rule_names_each_write_method_of_the_request_classifier() -> None:
    """`RoadmapServiceGitHubWritesHigh` counts the methods that `is_write_request` calls a REST
    write, each by name, and no other (#2574).

    PromQL reads an absent label as the empty string, so a negative matcher such as
    `method!="GET"` counts each request of a series with no `method` label as a write. A matcher
    that names the write methods counts none of them, and must name each write the code sends.
    """
    (rule,) = [
        rule
        for rule in _group(ROADMAP_SERVICE_ACTIVITY_GROUP)
        if rule["alert"] == "RoadmapServiceGitHubWritesHigh"
    ]
    assert [
        frozenset(methods.split("|")) for methods in _METHOD_REGEX_MATCHER.findall(rule["expr"])
    ] == [CONST_GH_MUTATION_HTTP_METHODS] * 3


@cache
def _alerting_rows() -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Each body row of the Alerting table of `k8s/README.md`: its source line, and its cells as
    the GFM table rule of markdown-it-py renders them. The rule keeps as many cells of a row as
    the header has, and drops the rest."""
    text = K8S_README.read_text(encoding="utf-8")
    lines = text.splitlines()
    nodes = SyntaxTreeNode(MarkdownIt("commonmark").enable("table").parse(text)).children
    heading = next(
        index
        for index, node in enumerate(nodes)
        if node.tag == "h2" and node.children[0].content == "Alerting"
    )
    table = next(node for node in nodes[heading:] if node.type == "table")
    (body,) = [node for node in table.children if node.type == "tbody"]
    return tuple(
        (
            lines[row.map[0]] if row.map else "",
            tuple(cell.children[0].content for cell in row.children),
        )
        for row in body.children
    )


def test_each_row_of_the_alerting_table_renders_every_cell() -> None:
    """GFM drops a cell past the last column of the header, so a reader does not see it (#5338).
    A row renders every cell when its source line ends with its last rendered cell."""
    rows = _alerting_rows()
    dropped = [
        cells[0]
        for line, cells in rows
        if not line.rstrip().removesuffix("|").rstrip().endswith(cells[-1])
    ]
    assert rows
    assert dropped == []


@pytest.mark.live("promtool")
def test_promtool_accepts_every_alert_rule(tmp_path: Path) -> None:
    """`promtool check rules` accepts each rule file the server loads, with each expression and
    each annotation template (#2472, #5292)."""
    paths = []
    for key, rules in _rule_files().items():
        path = tmp_path / key
        path.write_text(yaml.safe_dump(rules), encoding="utf-8")
        paths.append(path)
    result = promtool("check", "rules", *paths)
    assert (len(paths) > 0, result.returncode) == (True, 0), result.stdout + result.stderr


def _tested_alerts(rule_tests: Path) -> set[str]:
    """The alerts that the cases of a file of promtool unit tests name."""
    unit_tests = yaml.safe_load(rule_tests.read_text(encoding="utf-8"))
    return {
        case["alertname"]
        for test in unit_tests["tests"]
        for case in test.get("alert_rule_test", [])
    }


@pytest.mark.parametrize("group", tuple(dict.fromkeys(group for group, _ in RULE_GROUP_TESTS)))
def test_the_promtool_files_of_a_group_test_every_alert_of_the_group(group: str) -> None:
    """The files of promtool unit tests of a group test each of its alerts, and no other."""
    tested = set().union(
        *(_tested_alerts(path) for name, path in RULE_GROUP_TESTS if name == group)
    )
    # A recording rule holds no `alert` key, and a file of its cases holds no `alert_rule_test`.
    assert sorted(tested) == sorted(
        alert for alert in (rule.get("alert") for rule in _group(group)) if alert is not None
    )


@pytest.mark.parametrize(("group", "rule_tests"), RULE_GROUP_TESTS, ids=RULE_TEST_IDS)
def test_no_promtool_case_evaluates_more_rounds_than_the_budget(
    group: str, rule_tests: Path
) -> None:
    """Each case of a file of promtool unit tests ends within `MAX_PROMTOOL_ROUNDS` evaluations
    of its group (#4456): its last `eval_time` over the `evaluation_interval` of the file."""
    unit_tests = yaml.safe_load(rule_tests.read_text(encoding="utf-8"))
    step = parse_duration(str(unit_tests.get("evaluation_interval", "1m")))
    rounds = {
        test["name"]: max(
            parse_duration(str(case["eval_time"]))
            for case in (*test.get("alert_rule_test", []), *test.get("promql_expr_test", []))
        )
        / step
        for test in unit_tests["tests"]
    }
    assert {name: n for name, n in rounds.items() if n > MAX_PROMTOOL_ROUNDS} == {}, group


@pytest.mark.live("promtool")
@pytest.mark.parametrize(("group", "rule_tests"), RULE_GROUP_TESTS, ids=RULE_TEST_IDS)
def test_each_unit_tested_rule_fires_on_a_sample_and_stays_quiet_on_a_normal_series(
    group: str, rule_tests: Path, tmp_path: Path
) -> None:
    """`promtool test rules` passes the unit tests of each rule of `roadmap-service` (#2472), of
    `roadmap-service-recording` (#4562), of `roadmap-service-webhooks` (#2476), of
    `roadmap-service-activity` (#2475), of `roadmap-service-items` (#2919), of
    `roadmap-service-tools` (#3240), of `crawl4ai` (#3893), of
    `otel-collector` (#1642), of `valkey-memory` (#2094), of `research` (#3899), of `repos-drift`
    (#6783), of `ai-spend` (#4222), of `llm-gateway-db` (#4994) and of `metric-streams` (#4697).

    Each alert fires on a sample series with the labels and annotations it pins, and stays quiet
    on a normal series, before its wait ends, and on the series it must not count. Each file
    tests alerts of its group only.
    """
    unit_tests = yaml.safe_load(rule_tests.read_text(encoding="utf-8"))
    (rule_file,) = unit_tests["rule_files"]
    groups = _groups()
    (tmp_path / rule_file).write_text(
        yaml.safe_dump({"groups": [g for g in groups if g["name"] == group]}),
        encoding="utf-8",
    )
    copy = tmp_path / rule_tests.name
    copy.write_text(rule_tests.read_text(encoding="utf-8"), encoding="utf-8")
    result = promtool("test", "rules", copy)
    assert (
        sorted(_tested_alerts(rule_tests) - {rule.get("alert") for rule in _group(group)}),
        result.returncode,
    ) == ([], 0), result.stdout + result.stderr


def test_github_requests_high_action_does_not_lower_budget() -> None:
    """The action of `RoadmapServiceGitHubRequestsHigh` names no lower budget. The alert follows
    the budget, so a lower budget makes the alert fire sooner (#3495)."""
    document = CLUSTER_DOC.read_text(encoding="utf-8")
    row = next(
        line
        for line in document.splitlines()
        if line.startswith("| `RoadmapServiceGitHubRequestsHigh` |")
    )

    assert "lower the budget" not in row.lower()


# A Sloth `prometheus/v1` spec of one SLO, in the shape that `k8s/devops/monitoring/slos/` holds
# (#4709): the service of the catalog, one SLO with its objective, and the two event queries of its
# SLI over the `{{.window}}` placeholder. The renderer of the SLO groups is new in #4709, so each
# test below imports the function it calls when it runs.
SLO_SPEC = """\
version: "prometheus/v1"
service: roadmap-service
slos:
  - name: rounds
    objective: 99
    description: The rounds of a row that end well.
    sli:
      events:
        error_query: sum by (repo, row) (increase(devops_cli_service_jobs_total{result="error"}[{{.window}}]))
        total_query: sum by (repo, row) (increase(devops_cli_service_jobs_total{result=~"success|error"}[{{.window}}]))
    alerting:
      name: RoadmapServiceRounds
"""
# The spec of a service whose SLI groups by no label, as the requests of the LLM gateway do: the
# total query is a bare `sum`.
SLO_SPEC_WITHOUT_GROUPING = """\
version: "prometheus/v1"
service: llm-gateway
slos:
  - name: requests
    objective: 99.5
    description: The requests of the LLM gateway that succeed.
    sli:
      events:
        error_query: sum(increase(litellm_proxy_failed_requests_metric_total[{{.window}}]))
        total_query: sum(increase(litellm_proxy_total_requests_metric_total[{{.window}}]))
    alerting:
      name: LlmGatewayRequests
"""


def _slo_specs(
    tmp_path: Path, text: str = SLO_SPEC, stem: str = "roadmap-service-rounds"
) -> list[SloSpec]:
    """Write one spec of `text` as `<stem>.yaml` in `tmp_path` and load the folder."""
    from devops_cli.prometheus.slo_rules import load_slo_specs

    (tmp_path / f"{stem}.yaml").write_text(text, encoding="utf-8")
    return load_slo_specs(tmp_path)


def test_render_slo_groups_gives_each_alert_the_event_guard(tmp_path: Path) -> None:
    """A spec renders one group: a recording rule for each name of `SLO_RECORD_NAMES`, then the
    four burn-rate alerts of Table 2 of the SRE guideline, each with the severity of its row and
    the guard of the low-sample rule (#4709)."""
    from devops_cli.prometheus.slo_rules import (
        SLO_BURN_RATE_ROWS,
        SLO_MIN_EVENTS,
        SLO_RECORD_NAMES,
        SLO_WINDOW_DAYS,
        render_slo_groups,
    )

    (spec,) = _slo_specs(tmp_path)
    (group,) = render_slo_groups([spec])

    assert (SLO_WINDOW_DAYS, SLO_MIN_EVENTS) == (28, 20)
    assert group["name"] == "slo-roadmap-service-rounds"
    recording = [rule for rule in group["rules"] if "record" in rule]
    # The group records the seven error ratios, then the objective, its error budget and the
    # window.
    assert list(SLO_RECORD_NAMES) == [
        "slo:sli_error:ratio_rate5m",
        "slo:sli_error:ratio_rate30m",
        "slo:sli_error:ratio_rate1h",
        "slo:sli_error:ratio_rate2h",
        "slo:sli_error:ratio_rate6h",
        "slo:sli_error:ratio_rate1d",
        "slo:sli_error:ratio_rate3d",
        "slo:objective:ratio",
        "slo:error_budget:ratio",
        "slo:time_period:days",
    ]
    assert [rule["record"] for rule in recording] == list(SLO_RECORD_NAMES)
    # Each recorded series names its service and its SLO, so the four groups stay apart.
    assert {tuple(sorted(rule["labels"].items())) for rule in recording} == {
        (("service", "roadmap-service"), ("slo", "rounds"))
    }
    # The ratio of a window divides the two event queries over that window.
    assert {rule["record"]: rule["expr"] for rule in recording}["slo:sli_error:ratio_rate1h"] == (
        '(sum by (repo, row) (increase(devops_cli_service_jobs_total{result="error"}[1h])))'
        " / "
        '(sum by (repo, row) (increase(devops_cli_service_jobs_total{result=~"success|error"}[1h])))'
    )
    # The objective, its error budget and the window are the constants of the spec.
    assert [rule["expr"] for rule in recording if rule["record"] == "slo:objective:ratio"] == [
        "vector(0.99)"
    ]
    assert [rule["expr"] for rule in recording if rule["record"] == "slo:error_budget:ratio"] == [
        "vector(0.01)"
    ]
    assert [rule["expr"] for rule in recording if rule["record"] == "slo:time_period:days"] == [
        "vector(28)"
    ]
    alerts = [rule for rule in group["rules"] if "alert" in rule]
    assert [alert["alert"] for alert in alerts] == [
        "RoadmapServiceRoundsPage1h",
        "RoadmapServiceRoundsPage6h",
        "RoadmapServiceRoundsTicket1d",
        "RoadmapServiceRoundsTicket3d",
    ]
    assert [alert["labels"] for alert in alerts] == [
        {"severity": "critical"},
        {"severity": "critical"},
        {"severity": "warning"},
        {"severity": "warning"},
    ]
    # No alert waits: its expression already holds both of its windows.
    assert [alert.get("for") for alert in alerts] == [None] * len(SLO_BURN_RATE_ROWS)
    # The rows are the four rows of Table 2 of `docs/guidelines/sre.md`.
    assert [
        (row.long_window, row.short_window, str(row.burn_rate)) for row in SLO_BURN_RATE_ROWS
    ] == [("1h", "5m", "13.44"), ("6h", "30m", "5.6"), ("1d", "2h", "2.8"), ("3d", "6h", "0.93")]
    # Each alert needs both of its ratios above its burn rate, and its long window holds the
    # events of the low-sample rule. The count guard matches on the grouping of the spec.
    assert alerts[0]["expr"] == (
        "(\n"
        '  slo:sli_error:ratio_rate1h{service="roadmap-service", slo="rounds"} > (13.44 * 0.01)\n'
        "  and\n"
        '  slo:sli_error:ratio_rate5m{service="roadmap-service", slo="rounds"} > (13.44 * 0.01)\n'
        ")\n"
        "and on (repo, row) (sum by (repo, row) "
        '(increase(devops_cli_service_jobs_total{result=~"success|error"}[1h])) >= 20)'
    )
    assert [
        (
            f"slo:sli_error:ratio_rate{row.long_window}" in alert["expr"],
            f"slo:sli_error:ratio_rate{row.short_window}" in alert["expr"],
            alert["expr"].rsplit("\n", 1)[-1],
        )
        for alert, row in zip(alerts, SLO_BURN_RATE_ROWS, strict=True)
    ] == [
        (
            True,
            True,
            "and on (repo, row) (sum by (repo, row) "
            '(increase(devops_cli_service_jobs_total{result=~"success|error"}'
            f"[{row.long_window}])) >= 20)",
        )
        for row in SLO_BURN_RATE_ROWS
    ]


def test_a_spec_with_no_grouping_guards_each_alert_on_no_label(tmp_path: Path) -> None:
    """A total query with no `by` groups by no label, so the count guard matches on no label
    either: a plain `and` would compare two label sets that differ, and the alert would never
    fire (#4709)."""
    from devops_cli.prometheus.slo_rules import render_slo_groups

    (spec,) = _slo_specs(tmp_path, SLO_SPEC_WITHOUT_GROUPING, "llm-gateway-requests")
    (group,) = render_slo_groups([spec])

    assert spec.grouping == frozenset()
    assert [rule["expr"].rsplit("\n", 1)[-1] for rule in group["rules"] if "alert" in rule] == [
        "and on () (sum(increase(litellm_proxy_total_requests_metric_total[1h])) >= 20)",
        "and on () (sum(increase(litellm_proxy_total_requests_metric_total[6h])) >= 20)",
        "and on () (sum(increase(litellm_proxy_total_requests_metric_total[1d])) >= 20)",
        "and on () (sum(increase(litellm_proxy_total_requests_metric_total[3d])) >= 20)",
    ]


def test_write_slo_groups_replaces_only_the_text_between_the_markers(tmp_path: Path) -> None:
    """The values file keeps its other groups and keys: `write_slo_groups` replaces the text
    between the two marker comments, and nothing else (#4709)."""
    from devops_cli.prometheus.slo_rules import (
        SLO_GROUPS_END_MARKER,
        SLO_GROUPS_START_MARKER,
        write_slo_groups,
    )

    values = tmp_path / "prometheus-rules-values.yaml"
    values.write_text(
        "serverFiles:\n"
        "  devops_cli_alerting_rules.yml:\n"
        "    groups:\n"
        "      - name: roadmap-service\n"
        f"      {SLO_GROUPS_START_MARKER}\n"
        "      - name: stale\n"
        f"      {SLO_GROUPS_END_MARKER}\n"
        "  other.yml:\n"
        "    groups: []\n",
        encoding="utf-8",
    )

    write_slo_groups(values, [{"name": "slo-roadmap-service-rounds", "rules": []}])

    text = values.read_text(encoding="utf-8")
    assert "stale" not in text
    assert yaml.safe_load(text) == {
        "serverFiles": {
            "devops_cli_alerting_rules.yml": {
                "groups": [
                    {"name": "roadmap-service"},
                    {"name": "slo-roadmap-service-rounds", "rules": []},
                ]
            },
            "other.yml": {"groups": []},
        }
    }


def test_load_slo_specs_refuses_two_specs_of_one_service_and_name(tmp_path: Path) -> None:
    """Two specs of one service and one SLO name record one series name twice, so the load
    refuses the pair (#4709)."""
    from devops_cli.prometheus.slo_rules import load_slo_specs

    (tmp_path / "first.yaml").write_text(SLO_SPEC, encoding="utf-8")
    (tmp_path / "second.yaml").write_text(SLO_SPEC, encoding="utf-8")

    with pytest.raises(ConfigurationError, match="roadmap-service"):
        load_slo_specs(tmp_path)


def test_load_slo_specs_names_the_field_that_a_spec_does_not_hold(tmp_path: Path) -> None:
    """A spec that holds no total query is refused with its file and the key (#4709)."""
    from devops_cli.prometheus.slo_rules import load_slo_specs

    (tmp_path / "broken.yaml").write_text(
        SLO_SPEC.replace("        total_query:", "        valid_events:"), encoding="utf-8"
    )

    with pytest.raises(ConfigurationError, match="total_query"):
        load_slo_specs(tmp_path)


def test_load_slo_specs_refuses_a_spec_that_holds_two_slos(tmp_path: Path) -> None:
    """A spec holds one SLO: a second one would render a second group of the same file (#4709)."""
    from devops_cli.prometheus.slo_rules import load_slo_specs

    (tmp_path / "two.yaml").write_text(
        SLO_SPEC + "  - name: second\n    objective: 99\n", encoding="utf-8"
    )

    with pytest.raises(ConfigurationError, match="one SLO"):
        load_slo_specs(tmp_path)


def test_a_spec_with_no_alerting_name_names_its_alerts_after_its_file(tmp_path: Path) -> None:
    """A spec that names no `alerting.name` takes the stem of its file, so the alerts of
    `llm-gateway-latency.yaml` start with `LlmGatewayLatency` (#4709)."""
    from devops_cli.prometheus.slo_rules import render_slo_groups

    text = SLO_SPEC_WITHOUT_GROUPING.replace("    alerting:\n      name: LlmGatewayRequests\n", "")
    (spec,) = _slo_specs(tmp_path, text, "llm-gateway-latency")

    (group,) = render_slo_groups([spec])

    assert next(rule["alert"] for rule in group["rules"] if "alert" in rule) == (
        "LlmGatewayLatencyPage1h"
    )


def test_write_slo_groups_refuses_a_values_file_with_no_marker(tmp_path: Path) -> None:
    """A values file with no marker gets no render: the write names the missing marker (#4709)."""
    from devops_cli.prometheus.slo_rules import write_slo_groups

    values = tmp_path / "values.yaml"
    values.write_text(
        "serverFiles:\n  devops_cli_alerting_rules.yml:\n    groups: []\n", encoding="utf-8"
    )

    with pytest.raises(ConfigurationError, match="BEGIN slo-rules"):
        write_slo_groups(values, [])


def test_main_writes_the_render_of_a_folder_only_when_it_is_asked(tmp_path: Path) -> None:
    """The module prints the groups without `--write`, and writes them between the markers
    with it (#4709)."""
    from devops_cli.prometheus.slo_rules import (
        SLO_GROUPS_END_MARKER,
        SLO_GROUPS_START_MARKER,
        load_slo_specs,
        main,
        render_slo_groups,
    )

    specs = tmp_path / "specs"
    specs.mkdir()
    (specs / "roadmap-service-rounds.yaml").write_text(SLO_SPEC, encoding="utf-8")
    values = tmp_path / "values.yaml"
    values.write_text(
        f"groups:\n  {SLO_GROUPS_START_MARKER}\n  {SLO_GROUPS_END_MARKER}\n", encoding="utf-8"
    )
    before = values.read_text(encoding="utf-8")

    main([str(specs), str(values)])

    assert values.read_text(encoding="utf-8") == before
    main([str(specs), str(values), "--write"])
    assert yaml.safe_load(values.read_text(encoding="utf-8")) == {
        "groups": render_slo_groups(load_slo_specs(specs))
    }
