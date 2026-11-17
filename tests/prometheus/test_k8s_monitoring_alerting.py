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

The checks read files only, except the two that run the pinned promtool (`tools.lock`):
`promtool check rules` over every rule, and `promtool test rules` over each group that has unit
tests in `tests/fixtures/prometheus_rules/`. Each skips where promtool is
not installed; CI's test job installs it.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path, PurePosixPath
from typing import Any

import pytest
import yaml
from markdown_it import MarkdownIt
from markdown_it.tree import SyntaxTreeNode

from devops_cli.config.constants import (
    CONST_GH_MUTATION_HTTP_METHODS,
    CONST_SERVICE_METRIC_BUDGET_LIMIT,
    CONST_SERVICE_METRIC_FIX_CHECKS_JOBS,
    CONST_SERVICE_METRIC_IDENTITY_REFUSED,
    CONST_SERVICE_METRIC_JOB_RETRY_AFTER_SECONDS,
    CONST_SERVICE_METRIC_JOB_START_TIMESTAMP,
    CONST_SERVICE_METRIC_JOB_SUSPENDED,
    CONST_SERVICE_METRIC_JOBS,
    CONST_SERVICE_METRIC_WEBHOOK_DELIVERIES,
    CONST_SERVICE_METRIC_WEBHOOK_DELIVERY_FAILURES,
)
from devops_cli.prometheus.client import parse_duration
from devops_cli.prometheus.promql import selectors
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

K8S = REPO_ROOT / "k8s"
K8S_README = K8S / "README.md"
CLUSTER_DOC = REPO_ROOT / "docs" / "CLUSTER.md"
PROMETHEUS_VALUES = K8S / "monitoring" / "prometheus-values.yaml"
PRODUCT_RULES_VALUES = K8S / "devops" / "monitoring" / "prometheus-rules-values.yaml"
ROADMAP_SERVICE_RULE_TESTS = FIXTURES / "prometheus_rules" / "roadmap_service_tests.yaml"
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
AI_SPEND_RULE_TESTS = FIXTURES / "prometheus_rules" / "ai_spend_tests.yaml"
GATEWAY_DATABASE_RULE_TESTS = FIXTURES / "prometheus_rules" / "llm_gateway_db_tests.yaml"
METRIC_STREAMS_RULE_TESTS = FIXTURES / "prometheus_rules" / "metric_streams_tests.yaml"

ROADMAP_SERVICE_GROUP = "roadmap-service"
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
# The rules over the daily USD spend of the hosted models (#4222).
AI_SPEND_GROUP = "ai-spend"
# The rule of two metric streams that write one Prometheus series (#4697).
METRIC_STREAMS_GROUP = "metric-streams"
# The rules of the database of the LLM gateway, a CloudNativePG Cluster of one instance (#4994).
GATEWAY_DATABASE_GROUP = "llm-gateway-db"
# Each group whose rules have promtool unit tests, with a file of its tests.
RULE_GROUP_TESTS = (
    *ROADMAP_SERVICE_GROUP_TESTS,
    (CRAWL4AI_GROUP, CRAWL4AI_RULE_TESTS),
    (OTEL_COLLECTOR_GROUP, OTEL_COLLECTOR_RULE_TESTS),
    (VALKEY_MEMORY_GROUP, VALKEY_MEMORY_RULE_TESTS),
    (RESEARCH_GROUP, RESEARCH_RULE_TESTS),
    (AI_SPEND_GROUP, AI_SPEND_RULE_TESTS),
    (GATEWAY_DATABASE_GROUP, GATEWAY_DATABASE_RULE_TESTS),
    (METRIC_STREAMS_GROUP, METRIC_STREAMS_RULE_TESTS),
)
RULE_TEST_IDS = [rule_tests.stem for _, rule_tests in RULE_GROUP_TESTS]
# promtool evaluates the rules of a group once each `evaluation_interval` of a file, from 0 to
# the last `eval_time` of a case. A case of 150 hours at 1 minute made 9,000 rounds of a group
# of 4 rules and took 64 s on a CI runner (#4456). The longest case of the other files makes 390.
MAX_PROMTOOL_ROUNDS = 1_000

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
        CONST_SERVICE_METRIC_IDENTITY_REFUSED,
        CONST_SERVICE_METRIC_JOBS,
        CONST_SERVICE_METRIC_JOB_START_TIMESTAMP,
        # The fix-checks Jobs that the watch row starts and reports (#5027).
        CONST_SERVICE_METRIC_FIX_CHECKS_JOBS,
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
        # The items that the alternatives check has not checked, sent by its row (#2950).
        ROADMAP_ALTERNATIVES_UNCHECKED_ITEMS.name,
        # The calls of the stage planner's tools, and its plan runs (#3240).
        ROADMAP_TOOL_CALLS_PER_RUN.name,
        ROADMAP_TOOL_CALLS_TOTAL.name,
        # Freshness of the in-cluster RAG ingest runs (#1653).
        RAG_INGEST_LAST_SUCCESS_TIMESTAMP.name,
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
    """Every alerting rule the Prometheus server loads."""
    return [rule for group in _groups() for rule in group["rules"]]


def _group(name: str) -> list[dict[str, Any]]:
    """The alerting rules of one group, in file order."""
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


def test_every_alert_rule_selects_only_series_the_stack_serves() -> None:
    """A rule over a series no scrape serves stays silent, or fires on the missing target."""
    rules = _rules()
    assert (len(rules) > 0, [v for rule in rules for v in _unserved(rule["expr"])]) == (True, [])


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
    assert sorted(tested) == sorted(rule["alert"] for rule in _group(group))


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
    `roadmap-service-webhooks` (#2476), of `roadmap-service-activity` (#2475), of
    `roadmap-service-items` (#2919), of `roadmap-service-tools` (#3240), of `crawl4ai` (#3893), of
    `otel-collector` (#1642), of `valkey-memory` (#2094), of `research` (#3899), of `ai-spend`
    (#4222), of `llm-gateway-db` (#4994) and of `metric-streams` (#4697).

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
        sorted(_tested_alerts(rule_tests) - {rule["alert"] for rule in _group(group)}),
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
