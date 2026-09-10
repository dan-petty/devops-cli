"""Table formatters and domain TablePayload builders."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from devops_cli.config.defaults import DEFAULT_TABLE_BORDER_STYLE
from devops_cli.lang import MESSAGES
from devops_cli.output.formatters.scalars import (
    SEV_COLOR_MAP,
    format_duration,
    format_timestamp_age,
)

if TYPE_CHECKING:
    from rich.table import Table

    from devops_cli.output.models import TablePayload


def _add_table_column(table: Any, col: Any) -> None:
    """Add a column to a Rich Table instance handling models, tuples, and strings."""
    if hasattr(col, "header"):
        table.add_column(
            col.header,
            style=col.style,
            justify=getattr(col, "justify", "left"),
            width=getattr(col, "width", None),
            no_wrap=getattr(col, "no_wrap", False),
        )
        return

    if isinstance(col, (tuple, list)):
        if len(col) >= 2:
            name, style = col[0], col[1]
            if isinstance(style, int):
                table.add_column(str(name), width=style)
            elif str(style).lower() in ("left", "center", "right", "full"):
                table.add_column(str(name), justify=str(style).lower())
            else:
                table.add_column(str(name), style=str(style))
        elif len(col) == 1:
            table.add_column(str(col[0]))
        return

    table.add_column(str(col))


def render_table(
    title: str | Any = "",
    columns: Sequence[Any] | None = None,
    rows: Sequence[Sequence[Any]] | None = None,
    *,
    border_style: str | None = DEFAULT_TABLE_BORDER_STYLE,
    box_style: Any = None,
) -> Table:
    """Construct a styled Rich Table from columns and rows or TablePayload."""
    from rich.table import Table

    if hasattr(title, "render") and callable(getattr(title, "render")):
        rendered = title.render()
        if isinstance(rendered, Table):
            return rendered
    if hasattr(title, "to_table_payload") and callable(getattr(title, "to_table_payload")):
        payload = title.to_table_payload()
        if hasattr(payload, "render") and callable(getattr(payload, "render")):
            rendered = payload.render()
            if isinstance(rendered, Table):
                return rendered

    effective_title = str(getattr(title, "title", title)) if not isinstance(title, str) else title
    effective_cols = columns or getattr(title, "columns", None) or []
    effective_rows = rows or getattr(title, "rows", None) or []
    effective_border = getattr(title, "border_style", border_style)
    effective_box = getattr(title, "box_style", box_style)

    table = Table(
        title=effective_title,
        border_style=effective_border,
        box=effective_box,
        title_style="bold cyan",
        header_style="bold",
    )
    for col in effective_cols:
        _add_table_column(table, col)

    for row in effective_rows:
        table.add_row(*[str(cell) for cell in row])

    return table


def format_review_findings_table(findings: list[Any]) -> TablePayload:
    """Build a structured TablePayload of code review findings."""
    from devops_cli.output.console import escape_text
    from devops_cli.output.models import TableColumn, TablePayload

    columns: list[TableColumn | str | tuple[str, str | int]] = [
        TableColumn(header="Sev"),
        TableColumn(header="Location", style="dim"),
        TableColumn(header="Title"),
        TableColumn(header="✓"),
    ]
    rows: list[list[str]] = []
    for finding in findings:
        color = SEV_COLOR_MAP.get(getattr(finding, "severity", ""), "white")
        is_verified = getattr(finding, "verified", False)
        is_mitigated = getattr(finding, "mitigated", False)
        mark = (
            "[green]✓[/green]"
            if is_verified and not is_mitigated
            else "[yellow]~[/yellow]"
            if is_mitigated
            else "[dim]?[/dim]"
        )
        sev_str = str(getattr(finding, "severity", ""))
        loc_str = str(getattr(finding, "location", ""))
        title_str = str(getattr(finding, "title", ""))
        rows.append(
            [
                f"[{color}]{escape_text(sev_str)}[/{color}]",
                escape_text(loc_str),
                escape_text(title_str),
                mark,
            ]
        )
    return TablePayload(columns=columns, rows=rows, border_style=None)


def format_dependencies_table(deps: list[Any]) -> TablePayload:
    """Build a structured TablePayload of audited external dependencies."""
    from devops_cli.output.console import escape_text
    from devops_cli.output.models import TableColumn, TablePayload

    columns: list[TableColumn | str | tuple[str, str | int]] = [
        TableColumn(header="Severity"),
        TableColumn(header="Dependency", style="bold cyan"),
        TableColumn(header="Version Range"),
        TableColumn(header="Ecosystem"),
        TableColumn(header="Security Status"),
        TableColumn(header="Location", style="dim"),
    ]
    rows: list[list[str]] = []
    for dependency in deps:
        sev = getattr(dependency, "severity", "INFO")
        sev_upper = str(sev).upper()
        color = SEV_COLOR_MAP.get(sev_upper, "green")
        name = getattr(dependency, "name", str(dependency))
        version_range = getattr(dependency, "version_range", "any")
        ecosystem = getattr(dependency, "ecosystem", "-")
        status_val = getattr(dependency, "security_status", "Clean")
        loc_str = getattr(dependency, "location", "-")
        rows.append(
            [
                f"[{color}]{sev_upper}[/{color}]",
                escape_text(str(name)),
                escape_text(str(version_range)),
                escape_text(str(ecosystem)),
                f"[{color}]{escape_text(str(status_val))}[/{color}]",
                escape_text(str(loc_str)),
            ]
        )
    return TablePayload(
        title=MESSAGES.review.table_title_dependencies,
        columns=columns,
        rows=rows,
    )


def format_network_references_table(refs: list[Any]) -> TablePayload:
    """Build a structured TablePayload of audited network and egress references."""
    from devops_cli.output.console import escape_text
    from devops_cli.output.models import TableColumn, TablePayload

    columns: list[TableColumn | str | tuple[str, str | int]] = [
        TableColumn(header="Status"),
        TableColumn(header="Target / Reference", style="bold cyan"),
        TableColumn(header="Type"),
        TableColumn(header="Scope"),
        TableColumn(header="Location", style="dim"),
    ]
    rows: list[list[str]] = []
    for network_reference in refs:
        is_local = getattr(network_reference, "is_local", False)
        scope_str = "[dim]Local[/dim]" if is_local else "[bold cyan]External[/bold cyan]"
        status_val = getattr(network_reference, "security_status", "Safe")
        color = "red" if "⚠️" in status_val or "RISK" in str(status_val).upper() else "green"
        target = getattr(network_reference, "target", str(network_reference))
        ref_type = getattr(network_reference, "reference_type", "domain")
        loc_str = getattr(network_reference, "location", "-")
        rows.append(
            [
                f"[{color}]{escape_text(str(status_val))}[/{color}]",
                escape_text(str(target)),
                escape_text(str(ref_type)),
                scope_str,
                escape_text(str(loc_str)),
            ]
        )
    return TablePayload(
        title=MESSAGES.review.table_title_network_references,
        columns=columns,
        rows=rows,
    )


def format_benchmark_leaderboard_table(report: Any) -> TablePayload:
    """Build a structured TablePayload for an AI benchmark leaderboard."""
    from devops_cli.output.models import TablePayload

    columns: list[Any] = [
        ("Rank", "bold"),
        ("Model", "cyan"),
        ("Score", "bold green"),
        ("Peer Score", "green"),
        "Accuracy",
        "Security",
        "Complete",
        "Clarity",
        ("Judge Wt", "magenta"),
        ("Latency", "dim"),
        ("Bias (Judge)", "dim"),
        ("Self-Bias", "yellow"),
    ]
    rows: list[list[str]] = []
    leaderboard = getattr(report, "leaderboard", [])
    for rank_index, model_summary in enumerate(leaderboard, start=1):
        rank_badge = (
            "🥇"
            if rank_index == 1
            else ("🥈" if rank_index == 2 else ("🥉" if rank_index == 3 else f"#{rank_index}"))
        )
        grading_bias = getattr(model_summary, "grading_strictness_index", 0.0)
        bias_str = f"+{grading_bias:.1f}%" if grading_bias > 0 else f"{grading_bias:.1f}%"
        self_bias = getattr(model_summary, "self_preference_bias", 0.0)
        if self_bias < -5.0:
            self_bias_str = f"[green]{self_bias:.1f}%[/green] (strict)"
        elif self_bias > 15.0:
            self_bias_str = f"[red]+{self_bias:.1f}%[/red] (inflated)"
        elif self_bias > 0:
            self_bias_str = f"+{self_bias:.1f}%"
        else:
            self_bias_str = f"{self_bias:.1f}%"
        rows.append(
            [
                rank_badge,
                getattr(model_summary, "model", ""),
                f"{getattr(model_summary, 'overall_percentage', 0.0):.1f}%",
                f"{getattr(model_summary, 'peer_only_percentage', 0.0):.1f}%",
                f"{getattr(model_summary, 'accuracy_avg', 0.0) * 10.0:.1f}%",
                f"{getattr(model_summary, 'security_avg', 0.0) * 10.0:.1f}%",
                f"{getattr(model_summary, 'completeness_avg', 0.0) * 10.0:.1f}%",
                f"{getattr(model_summary, 'clarity_avg', 0.0) * 10.0:.1f}%",
                f"{getattr(model_summary, 'judge_weight', 1.0):.2f}",
                format_duration(getattr(model_summary, "average_duration_seconds", 0.0)),
                bias_str,
                self_bias_str,
            ]
        )
    session_id = getattr(report, "session_id", "")
    return TablePayload(
        title=MESSAGES.benchmark.table_title_leaderboard.format(session_id=session_id),
        columns=columns,
        rows=rows,
    )


def _format_suite_leaderboard_row(rank_index: int, m: Any) -> list[str]:
    rank_badge = (
        "🥇"
        if rank_index == 1
        else ("🥈" if rank_index == 2 else ("🥉" if rank_index == 3 else f"#{rank_index}"))
    )
    hallucination_rate = getattr(m, "hallucination_rate", 0.0)
    hallucination_color = (
        "green"
        if hallucination_rate <= 0.05
        else ("yellow" if hallucination_rate <= 0.15 else "red")
    )
    hallucination_str = (
        f"[{hallucination_color}]{hallucination_rate * 100.0:.1f}%[/{hallucination_color}]"
    )

    compliance_rate = getattr(m, "architectural_compliance_rate", 1.0)
    compliance_color = "green" if compliance_rate >= 0.90 else "yellow"
    compliance_str = f"[{compliance_color}]{compliance_rate * 100.0:.1f}%[/{compliance_color}]"

    tp = getattr(m, "true_positives", 0)
    fp = getattr(m, "false_positives", 0)
    tn = getattr(m, "true_negatives", 0)
    fn = getattr(m, "false_negatives", 0)
    matrix_str = f"{tp}/{fp}/{tn}/{fn}"

    return [
        rank_badge,
        getattr(m, "model", ""),
        f"[bold green]{getattr(m, 'overall_score', 0.0):.1f}%[/bold green]",
        f"{getattr(m, 'precision', 0.0) * 100.0:.1f}%",
        f"{getattr(m, 'recall', 0.0) * 100.0:.1f}%",
        f"{getattr(m, 'f1_score', 0.0) * 100.0:.1f}%",
        hallucination_str,
        compliance_str,
        format_duration(getattr(m, "avg_latency_ms", 0.0) / 1000.0),
        f"{getattr(m, 'avg_tokens_per_second', 0.0):.1f} tps",
        matrix_str,
    ]


def format_benchmark_suite_table(report: Any) -> TablePayload:
    """Build structured TablePayload for multi-model benchmark evaluation suite leaderboard."""
    from devops_cli.output.models import TablePayload

    columns: list[Any] = [
        ("Rank", "bold"),
        ("Model", "cyan"),
        ("Overall", "bold green"),
        ("Precision", "green"),
        ("Recall", "green"),
        ("F1 Score", "bold cyan"),
        ("Hallucination", "yellow"),
        ("Arch Compl", "magenta"),
        ("Latency", "dim"),
        ("Throughput", "dim"),
        ("TP/FP/TN/FN", "blue"),
    ]
    rows: list[list[str]] = []
    leaderboard = getattr(report, "leaderboard", [])
    for rank_index, model_summary in enumerate(leaderboard, start=1):
        rows.append(_format_suite_leaderboard_row(rank_index, model_summary))

    session_id = getattr(report, "session_id", "")
    return TablePayload(
        title=MESSAGES.benchmark.table_title_suite_leaderboard.format(session_id=session_id),
        columns=columns,
        rows=rows,
    )


def format_benchmark_category_table(report: Any) -> TablePayload | None:
    """Build a structured TablePayload for domain category breakdown."""
    from devops_cli.output.models import TablePayload

    tasks_run = getattr(report, "tasks_run", [])
    if len(tasks_run) <= 1:
        return None
    categories = sorted({getattr(task, "category", "") for task in tasks_run})
    category_columns: list[Any] = [("Model", "cyan")]
    for category in categories:
        category_columns.append(category.capitalize())

    category_rows: list[list[str]] = []
    leaderboard = getattr(report, "leaderboard", [])
    for model_summary in leaderboard:
        row = [getattr(model_summary, "model", "")]
        cat_scores = getattr(model_summary, "category_scores", {})
        for category in categories:
            score = cat_scores.get(category, 0.0)
            row.append(f"{score:.1f}%")
        category_rows.append(row)

    session_id = getattr(report, "session_id", "")
    return TablePayload(
        title=MESSAGES.benchmark.table_title_category_breakdown.format(session_id=session_id),
        columns=category_columns,
        rows=category_rows,
    )


def format_benchmark_server_table(report: Any) -> TablePayload | None:
    """Build a structured TablePayload for Ollama server hardware & node performance."""
    from devops_cli.output.models import TablePayload

    servers = getattr(report, "server_benchmarks", [])
    if not servers:
        return None

    server_cols: list[Any] = [
        ("Server / Worker Node", "cyan"),
        ("Avg Latency", "bold yellow"),
        ("Speed Factor", "magenta"),
        ("Total Time", "dim"),
        ("Tasks", "dim"),
        ("Avg Score Given", "magenta"),
        "Server Bias",
        ("Per-Model Latency Breakdown", "dim"),
    ]

    fastest_latency = min(
        (
            getattr(s, "generation_duration_avg", 0.0)
            for s in servers
            if getattr(s, "generation_duration_avg", 0.0) > 0
        ),
        default=0.0,
    )

    server_rows: list[list[str]] = []
    multi_server = len(servers) > 1
    for s in servers:
        bias = getattr(s, "server_score_bias", 0.0)
        bias_str = f"+{bias:.1f}%" if bias > 0 else f"{bias:.1f}%"
        lat_dict = getattr(s, "model_latencies", {})
        lat_breakdown = ", ".join(f"{m.split(':')[0]}: {dur}s" for m, dur in lat_dict.items())
        gen_avg = getattr(s, "generation_duration_avg", 0.0)
        is_fastest = multi_server and fastest_latency > 0 and gen_avg == fastest_latency
        if is_fastest:
            speed_str = "[bold green]1.00x (fastest)[/bold green]"
        elif multi_server and fastest_latency > 0:
            speed_str = f"{gen_avg / fastest_latency:.2f}x slower"
        else:
            speed_str = "1.00x"

        server_rows.append(
            [
                getattr(s, "server", ""),
                format_duration(gen_avg),
                speed_str,
                format_duration(getattr(s, "total_duration_seconds", 0.0)),
                str(getattr(s, "tasks_generated_count", 0)),
                f"{getattr(s, 'avg_score_awarded', 0.0):.1f}%",
                bias_str,
                lat_breakdown or "-",
            ]
        )

    session_id = getattr(report, "session_id", "")
    return TablePayload(
        title=MESSAGES.benchmark.table_title_server_hardware.format(session_id=session_id),
        columns=server_cols,
        rows=server_rows,
    )


def format_k8s_pods_table(pods: Sequence[Any]) -> TablePayload:
    """Build a structured TablePayload for Kubernetes pod status."""
    from devops_cli.output.models import TableColumn, TablePayload

    columns: list[TableColumn | str | tuple[str, str | int]] = [
        TableColumn(header="Namespace", style="dim"),
        TableColumn(header="Name", style="cyan", no_wrap=True),
        TableColumn(header="Status"),
        TableColumn(header="Ready", justify="center"),
        TableColumn(header="Restarts", justify="right"),
        TableColumn(header="Age", justify="right"),
    ]
    rows: list[list[str]] = []
    for item in pods:
        if isinstance(item, (list, tuple)):
            rows.append([str(x) for x in item])
            continue
        metadata = getattr(item, "metadata", None)
        status = getattr(item, "status", None)
        spec = getattr(item, "spec", None)
        pod_ns = (getattr(metadata, "namespace", None) if metadata else None) or "default"
        pod_name = (getattr(metadata, "name", None) if metadata else None) or "—"
        phase = (getattr(status, "phase", None) if status else None) or "Unknown"
        created_at = (
            metadata.creation_timestamp.isoformat()
            if metadata and getattr(metadata, "creation_timestamp", None)
            else ""
        )
        containers = (getattr(spec, "containers", None) if spec else None) or []
        c_statuses = (getattr(status, "container_statuses", None) if status else None) or []
        ready_containers = sum(1 for cs in c_statuses if getattr(cs, "ready", False))
        restarts = sum(getattr(cs, "restart_count", 0) for cs in c_statuses)
        status_color = (
            "green" if phase == "Running" else ("yellow" if phase == "Pending" else "red")
        )
        rows.append(
            [
                pod_ns,
                pod_name,
                f"[{status_color}]{phase}[/{status_color}]",
                f"{ready_containers}/{len(containers)}",
                str(restarts),
                format_timestamp_age(created_at),
            ]
        )
    return TablePayload(
        title=MESSAGES.k8s.table_title_pods,
        columns=columns,
        rows=rows,
        show_header=True,
        header_style="bold cyan",
    )


def format_k8s_contexts_table(contexts: Sequence[Any], active_name: str = "") -> TablePayload:
    """Build a structured TablePayload for Kubernetes cluster contexts."""
    from devops_cli.output.models import TableColumn, TablePayload

    columns: list[TableColumn | str | tuple[str, str | int]] = [
        TableColumn(header="", width=2),
        TableColumn(header="Context", style="cyan"),
        TableColumn(header="Cluster"),
        TableColumn(header="User"),
    ]
    rows: list[list[str]] = []
    for ctx in contexts:
        if isinstance(ctx, (list, tuple)):
            rows.append([str(x) for x in ctx])
            continue
        if isinstance(ctx, dict):
            name = ctx.get("name", "")
            indicator = "[green]●[/green]" if name == active_name else ""
            ctx_data = ctx.get("context", {})
            rows.append(
                [
                    indicator,
                    name,
                    ctx_data.get("cluster", ""),
                    ctx_data.get("user", ""),
                ]
            )
        else:
            name = getattr(ctx, "name", str(ctx))
            indicator = "[green]●[/green]" if name == active_name else ""
            rows.append([indicator, name, "", ""])
    return TablePayload(
        title=MESSAGES.k8s.table_title_contexts,
        columns=columns,
        rows=rows,
    )


def format_k8s_nodes_table(nodes: Sequence[Any]) -> TablePayload:
    """Build a structured TablePayload for Kubernetes cluster nodes."""
    from devops_cli.config.constants import CONST_K8S_NODE_ROLE_LABEL_PREFIX
    from devops_cli.output.models import TableColumn, TablePayload

    columns: list[TableColumn | str | tuple[str, str | int]] = [
        TableColumn(header="Name", style="cyan"),
        TableColumn(header="Status"),
        TableColumn(header="Roles"),
        TableColumn(header="Version"),
    ]
    rows: list[list[str]] = []
    for node in nodes:
        if isinstance(node, (list, tuple)):
            rows.append([str(x) for x in node])
            continue
        metadata = getattr(node, "metadata", None)
        node_status = getattr(node, "status", None)
        name = getattr(metadata, "name", "—") if metadata else "—"
        conditions = getattr(node_status, "conditions", []) if node_status else []
        ready = next(
            (
                getattr(c, "status", "Unknown")
                for c in (conditions or [])
                if getattr(c, "type", None) == "Ready"
            ),
            "Unknown",
        )
        labels = getattr(metadata, "labels", {}) if metadata else {}
        roles = (
            ", ".join(
                label_key.removeprefix(CONST_K8S_NODE_ROLE_LABEL_PREFIX)
                for label_key in (labels or {})
                if label_key.startswith(CONST_K8S_NODE_ROLE_LABEL_PREFIX)
            )
            or "worker"
        )
        node_info = getattr(node_status, "node_info", None) if node_status else None
        version = getattr(node_info, "kubelet_version", "Unknown") if node_info else "Unknown"
        status_str = (
            f"[green]{MESSAGES.k8s.node_ready}[/green]"
            if ready == "True"
            else f"[red]{MESSAGES.k8s.node_not_ready}[/red]"
        )
        rows.append([name, status_str, roles, version])
    return TablePayload(
        title=MESSAGES.k8s.table_title_nodes,
        columns=columns,
        rows=rows,
    )


def format_k8s_rbac_table(rows: list[list[str]]) -> TablePayload:
    """Build a structured TablePayload for Kubernetes RBAC audit findings."""
    from devops_cli.output.models import TableColumn, TablePayload

    columns: list[TableColumn | str | tuple[str, str | int]] = [
        TableColumn(header="Namespace", style="cyan"),
        TableColumn(header="Binding", style="bold"),
        TableColumn(header="Role"),
        TableColumn(header="Severity"),
    ]
    return TablePayload(
        title=MESSAGES.k8s.table_title_rbac_audit,
        columns=columns,
        rows=rows,
    )


def format_k8s_lint_table(findings: list[Any], target_name: str) -> TablePayload:
    """Build a structured TablePayload for Kube-linter security audit findings."""
    from devops_cli.output.models import TableColumn, TablePayload

    columns: list[TableColumn | str | tuple[str, str | int]] = [
        TableColumn(header="Severity", style="bold yellow"),
        TableColumn(header="Resource Location"),
        TableColumn(header="Title"),
        TableColumn(header="Remediation"),
    ]
    rows = [
        [
            getattr(f, "severity", ""),
            getattr(f, "location", ""),
            getattr(f, "title", ""),
            getattr(f, "fix", None) or "-",
        ]
        for f in findings
    ]
    return TablePayload(
        title=f"{MESSAGES.k8s.table_title_kube_linter}: {target_name}",
        columns=columns,
        rows=rows,
    )


def format_k8s_schema_table(findings: list[Any], target_name: str) -> TablePayload:
    """Build a structured TablePayload for Kubeconform schema validation issues."""
    from devops_cli.output.models import TableColumn, TablePayload

    columns: list[TableColumn | str | tuple[str, str | int]] = [
        TableColumn(header="Severity", style="bold red"),
        TableColumn(header="Location"),
        TableColumn(header="Error"),
        TableColumn(header="Remediation"),
    ]
    rows = [
        [
            getattr(f, "severity", ""),
            getattr(f, "location", ""),
            getattr(f, "title", ""),
            getattr(f, "fix", None) or getattr(f, "description", "-"),
        ]
        for f in findings
    ]
    return TablePayload(
        title=f"{MESSAGES.k8s.table_title_kubeconform}: {target_name}",
        columns=columns,
        rows=rows,
    )


def format_k8s_policy_table(report: Any) -> TablePayload:
    """Build a structured TablePayload for admission policy violation reports."""
    from devops_cli.output.models import TableColumn, TablePayload

    columns: list[TableColumn | str | tuple[str, str | int]] = [
        TableColumn(header="Policy"),
        TableColumn(header="Rule"),
        TableColumn(header="Resource"),
        TableColumn(header="Status", style="bold red"),
        TableColumn(header="Message"),
    ]
    rows: list[list[str]] = []
    rule_results = getattr(report, "rule_results", [])
    for rule in rule_results:
        st = getattr(rule, "status", "")
        st_style = "green" if st in ("pass", "success") else "bold red"
        rows.append(
            [
                getattr(rule, "policy_name", ""),
                getattr(rule, "rule_name", ""),
                f"{getattr(rule, 'resource_kind', '')}/{getattr(rule, 'resource_name', '')}",
                f"[{st_style}]{st}[/{st_style}]",
                getattr(rule, "message", ""),
            ]
        )
    engine_str = str(getattr(report, "engine", "kyverno")).upper()
    return TablePayload(
        title=MESSAGES.k8s.table_title_policy_violations.format(engine=engine_str),
        columns=columns,
        rows=rows,
    )


def format_k8s_service_targets_table(configured: dict[str, str], stack: str) -> TablePayload:
    """Build a structured TablePayload for detected Kubernetes service endpoints."""
    from devops_cli.output.models import TableColumn, TablePayload

    columns: list[TableColumn | str | tuple[str, str | int]] = [
        TableColumn(header="Config Key / Service", style="cyan"),
        TableColumn(header="Detected Target URL", style="green"),
    ]
    rows = [[k, v] for k, v in configured.items()]
    return TablePayload(
        title=MESSAGES.k8s.table_title_configured_services.format(stack=stack),
        columns=columns,
        rows=rows,
    )


def format_k8s_tls_secrets_table(results: list[Any]) -> TablePayload:
    """Build a structured TablePayload for deployed Kubernetes TLS secrets."""
    from devops_cli.output.models import TableColumn, TablePayload

    columns: list[TableColumn | str | tuple[str, str | int]] = [
        TableColumn(header="Namespace", style="cyan"),
        TableColumn(header="Secret Name", style="white"),
        TableColumn(header="Status", style="bold"),
    ]
    rows: list[list[str]] = []
    for r in results:
        is_created = getattr(r, "created", False)
        err = getattr(r, "error", "")
        status_str = "[green]✓ Created[/green]" if is_created else f"[red]✗ Failed: {err}[/red]"
        ns = getattr(r, "namespace", "")
        sec_name = getattr(r, "secret_name", "")
        rows.append([ns, sec_name, status_str])
    return TablePayload(
        title=MESSAGES.k8s.table_title_tls_secrets,
        columns=columns,
        rows=rows,
    )


def format_docker_stats_table(rows: list[list[str]]) -> TablePayload:
    """Build a structured TablePayload for live Docker container stats."""
    from devops_cli.output.models import TableColumn, TablePayload

    columns: list[TableColumn | str | tuple[str, str | int]] = [
        TableColumn(header="Container", style="cyan", no_wrap=True),
        TableColumn(header="CPU %", justify="right"),
        TableColumn(header="MEM Usage / Limit", justify="right"),
        TableColumn(header="NET I/O (RX/TX)", justify="right"),
    ]
    return TablePayload(
        title=MESSAGES.docker.table_title_stats,
        columns=columns,
        rows=rows,
        show_header=True,
        header_style="bold cyan",
    )


def format_argo_apps_table(rows: list[list[str]]) -> TablePayload:
    """Build a structured TablePayload for ArgoCD applications."""
    from devops_cli.output.models import TableColumn, TablePayload

    columns: list[TableColumn | str | tuple[str, str | int]] = [
        TableColumn(header="Name", style="cyan"),
        TableColumn(header="Project"),
        TableColumn(header="Sync"),
        TableColumn(header="Health"),
        TableColumn(header="Repo", style="dim"),
    ]
    return TablePayload(
        title=MESSAGES.argo.table_title_apps,
        columns=columns,
        rows=rows,
        show_header=True,
        header_style="bold cyan",
    )


def format_ssh_keys_table(keys: Sequence[Any], rotation_days: int) -> TablePayload:
    """Build a structured TablePayload for managed SSH keys."""
    from devops_cli.config.constants import CONST_SSH_GRACE_DAYS
    from devops_cli.output.formatters.scalars import format_status_badge
    from devops_cli.output.models import TableColumn, TablePayload

    columns: list[TableColumn | str | tuple[str, str | int]] = [
        TableColumn(header="Key", style="cyan"),
        TableColumn(header="Age (days)", justify="right"),
        TableColumn(header="Status"),
    ]
    rows: list[list[str]] = []
    for key in keys:
        if isinstance(key, (list, tuple)):
            rows.append([str(x) for x in key])
            continue
        key_path = getattr(key, "path", None)
        key_name = (
            key_path.name
            if key_path and hasattr(key_path, "name")
            else str(getattr(key, "name", key))
        )
        age = getattr(key, "age_days", 0)
        age_val = age if age is not None else 0
        if age_val > rotation_days + CONST_SSH_GRACE_DAYS:
            status_text = format_status_badge("overdue for deletion")
        elif age_val > rotation_days:
            status_text = format_status_badge("grace period", warn_color="yellow")
        elif age_val > rotation_days - 7:
            status_text = format_status_badge("rotation soon", warn_color="yellow")
        else:
            status_text = format_status_badge("active")
        rows.append([key_name, str(age_val), status_text])

    return TablePayload(
        title=MESSAGES.ssh.table_title_managed_keys,
        columns=columns,
        rows=rows,
    )


def format_tf_status_table(
    target_name: str,
    target_dir: str,
    binary: str,
    initialized: bool,
    has_lock: bool,
    has_state: bool,
) -> TablePayload:
    """Build a structured TablePayload for OpenTofu / Terraform status."""
    from devops_cli.output.models import TableColumn, TablePayload

    columns: list[TableColumn | str | tuple[str, str | int]] = [
        TableColumn(header="Property", style="bold white"),
        TableColumn(header="Status / Value", style="green"),
    ]
    rows = [
        ["Directory", target_dir],
        ["Resolved Binary", binary],
        ["Initialized (.terraform)", "✓ Yes" if initialized else "[red]✗ No[/red]"],
        ["Lock File (.lock.hcl)", "✓ Yes" if has_lock else "[dim]None[/dim]"],
        ["Local State File", "✓ Yes" if has_state else "[dim]None[/dim]"],
    ]
    return TablePayload(
        title=MESSAGES.tf.table_title_status.format(name=target_name),
        columns=columns,
        rows=rows,
        border_style="cyan",
    )


def format_tflint_table(findings: Sequence[Any], target_name: str) -> TablePayload:
    """Build a structured TablePayload for TFLint findings."""
    from devops_cli.output.models import TableColumn, TablePayload

    columns: list[TableColumn | str | tuple[str, str | int]] = [
        TableColumn(header="Severity", style="bold"),
        TableColumn(header="Location"),
        TableColumn(header="Rule / Title"),
        TableColumn(header="Description"),
    ]
    rows: list[list[str]] = []
    for f in findings:
        if isinstance(f, (list, tuple)):
            rows.append([str(x) for x in f])
            continue
        rows.append(
            [
                getattr(f, "severity", ""),
                getattr(f, "location", ""),
                getattr(f, "title", ""),
                getattr(f, "description", ""),
            ]
        )
    return TablePayload(
        title=MESSAGES.tf.table_title_tflint.format(target=target_name),
        columns=columns,
        rows=rows,
    )


def format_argo_fleet_sync_table(result: Any) -> TablePayload:
    """Build a structured TablePayload for Argo multi-cluster fleet synchronization."""
    from devops_cli.output.models import TableColumn, TablePayload

    columns: list[TableColumn | str | tuple[str, str | int]] = [
        TableColumn(header="Cluster", style="bold cyan"),
        TableColumn(header="Application", style="bold"),
        TableColumn(header="Status"),
        TableColumn(header="Duration (s)", justify="right"),
        TableColumn(header="Message"),
    ]
    rows: list[list[str]] = []
    targets = getattr(result, "targets", [])
    for t in targets:
        st = getattr(t, "status", "Unknown")
        status_styled = f"[green]{st}[/green]" if st == "Synced" else f"[red]{st}[/red]"
        rows.append(
            [
                getattr(t, "cluster", ""),
                getattr(t, "app_name", ""),
                status_styled,
                f"{getattr(t, 'duration_seconds', 0.0):.2f}",
                getattr(t, "message", ""),
            ]
        )
    fleet_name = getattr(result, "fleet_name", "Fleet")
    synced = getattr(result, "total_synced", 0)
    failed = getattr(result, "total_failed", 0)
    return TablePayload(
        title=f"Argo Fleet Synchronization: {fleet_name} ({synced} synced, {failed} failed)",
        columns=columns,
        rows=rows,
    )


def format_argo_rollout_analysis_table(result: Any) -> TablePayload:
    """Build a structured TablePayload for Argo Rollout metric gate analysis."""
    from devops_cli.output.models import TableColumn, TablePayload

    columns: list[TableColumn | str | tuple[str, str | int]] = [
        TableColumn(header="Metric", style="bold cyan"),
        TableColumn(header="Value", justify="right"),
        TableColumn(header="Operator"),
        TableColumn(header="Threshold", justify="right"),
        TableColumn(header="Status"),
    ]
    rows: list[list[str]] = []
    metric_results = getattr(result, "metric_results", [])
    for m in metric_results:
        passed = m.get("passed", False) if isinstance(m, dict) else getattr(m, "passed", False)
        status_styled = "[green]PASSED[/green]" if passed else "[red]FAILED[/red]"
        metric_name = m.get("metric", "") if isinstance(m, dict) else getattr(m, "metric_name", "")
        val = m.get("value", 0.0) if isinstance(m, dict) else getattr(m, "value", 0.0)
        op = m.get("operator", "") if isinstance(m, dict) else getattr(m, "operator", "")
        thresh = m.get("threshold", 0.0) if isinstance(m, dict) else getattr(m, "threshold", 0.0)
        rows.append(
            [
                str(metric_name),
                f"{val:.3f}" if isinstance(val, (int, float)) else str(val),
                str(op),
                f"{thresh:.3f}" if isinstance(thresh, (int, float)) else str(thresh),
                status_styled,
            ]
        )
    rollout_name = getattr(result, "rollout_name", "Rollout")
    action = getattr(result, "action_taken", "None")
    return TablePayload(
        title=f"Argo Rollout Analysis: {rollout_name} (Action: {action.upper()})",
        columns=columns,
        rows=rows,
    )


def format_tf_cost_table(
    cost: Any,
    title: str | None = None,
) -> TablePayload:
    """Build a structured TablePayload for Infracost FinOps cost breakdown."""
    from devops_cli.output.models import TableColumn, TablePayload

    tbl_title = (
        title
        or f"Cloud Cost Breakdown: {getattr(cost, 'directory', 'tf')} ({getattr(cost, 'source', 'infracost')})"
    )
    columns: list[TableColumn | str | tuple[str, str | int]] = [
        TableColumn(header="Resource", style="cyan"),
        TableColumn(header="Type", style="magenta"),
        TableColumn(header="Hourly Cost", justify="right"),
        TableColumn(header="Monthly Cost", justify="right"),
    ]
    rows: list[list[str]] = []
    for res in getattr(cost, "resources", []):
        rows.append(
            [
                res.name,
                res.resource_type or "unknown",
                f"${res.hourly_cost:.2f}",
                f"${res.monthly_cost:.2f}",
            ]
        )
    rows.append(
        [
            "Total",
            getattr(cost, "currency", "USD"),
            f"${getattr(cost, 'total_hourly_cost', 0.0):.2f}",
            f"${getattr(cost, 'total_monthly_cost', 0.0):.2f}",
        ]
    )
    if getattr(cost, "diff_monthly_cost", None) is not None:
        diff = float(cost.diff_monthly_cost)
        diff_str = f"{'+' if diff >= 0 else ''}${diff:.2f}"
        rows.append(["Monthly Diff", getattr(cost, "currency", "USD"), "-", diff_str])

    return TablePayload(
        title=tbl_title,
        columns=columns,
        rows=rows,
        border_style="green",
    )
