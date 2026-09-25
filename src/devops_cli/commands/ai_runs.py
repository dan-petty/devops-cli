"""`devops ai runs`: benchmark and evaluation runs, kept in the data directory and shared (#554)."""

from __future__ import annotations

import json
from typing import Annotated, Any

import typer

from devops_cli.ai.run_store import (
    BaselineRecord,
    Mechanism,
    MetricDiff,
    RegressionReport,
    RegressionTolerances,
    RunComparison,
    RunIndex,
    RunIndexNotConfiguredError,
    RunRecord,
    SavedRun,
    check_regression,
    compare_runs,
    get_baseline,
    get_run,
    list_baselines,
    load_runs,
    runs_dir,
    set_baseline,
)
from devops_cli.config import options as opt
from devops_cli.config.constants import (
    CONST_OUTPUT_FORMAT_TABLE,
    CONST_RUNS_INDEX_NAMESPACE,
    CONST_RUNS_INDEX_SECRET,
    CONST_RUNS_INDEX_SERVICE,
)
from devops_cli.config.defaults import DEFAULT_VALKEY_PORT
from devops_cli.core.cli import new_typer
from devops_cli.exceptions.valkey import ValkeyError
from devops_cli.k8s.node_port import (
    NodePortSpec,
    ServiceNotReachableError,
    node_port_address,
    secret_value,
)
from devops_cli.lang.en.help import HELP
from devops_cli.output import (
    escape_text,
    get_stderr_console,
    print_error,
    print_info,
    print_section,
    print_success,
    print_table,
    print_warning,
)
from devops_cli.output.serialization import emit_serialized, normalize_format
from devops_cli.security.sanitizer import mask_secrets
from devops_cli.telemetry import trace_span

app = new_typer(
    help=HELP.ai.runs,
    no_args_is_help=True,
)


def announce_runs(saved: list[SavedRun], *, to_stderr: bool = False) -> None:
    """Say where runs were kept, and whether other workstations can see them.

    Commands writing JSON or Markdown to stdout announce on stderr, keeping their output parseable.
    """
    if not saved:
        return
    console = get_stderr_console() if to_stderr else None
    first = saved[0]
    kept = (
        f"{first.record.mechanism.value} run {first.record.run_id} → "
        f"[bold]{escape_text(str(first.path))}[/bold]"
        if len(saved) == 1
        else f"{len(saved)} {first.record.mechanism.value} runs → "
        f"[bold]{escape_text(str(first.path.parent))}[/bold]"
    )
    print_success(f"Saved {kept}", console=console)
    if not first.shared:
        print_info(
            f"Kept on this workstation only: {escape_text(first.detail)}.",
            prefix=False,
            console=console,
        )


def announce_run(saved: SavedRun, *, to_stderr: bool = False) -> None:
    """Say where a run was kept, and whether other workstations can see it."""
    announce_runs([saved], to_stderr=to_stderr)


@app.command("reindex")
@trace_span("ai.runs.reindex")
def reindex_cmd(
    mechanism: Annotated[
        Mechanism | None,
        typer.Option("--mechanism", "-m", help="Only index runs of this mechanism."),
    ] = None,
) -> None:
    """Rebuild the shared run index in Valkey from the run records in the data directory."""
    records = load_runs(mechanism)
    if not records:
        print_info(f"No runs recorded in {escape_text(str(runs_dir()))}.")
        return
    try:
        with RunIndex.from_settings() as index:
            count = index.put(*records)
            location = index.location
    except RunIndexNotConfiguredError as exc:
        print_error(exc.message)
        raise typer.Exit(code=1) from exc
    except ValkeyError as exc:
        print_error(f"The run index is unreachable: {mask_secrets(exc.message)}")
        raise typer.Exit(code=1) from exc
    print_success(f"Indexed {count} run(s) from {escape_text(str(runs_dir()))} at {location}.")


RUNS_INDEX = NodePortSpec(
    what="run index",
    port=DEFAULT_VALKEY_PORT,
    port_name="valkey",
    port_label="Valkey",
    manifest="k8s/llm/valkey-runs.yaml",
)


@app.command("connect")
@trace_span("ai.runs.connect")
def connect_cmd(
    context: Annotated[
        str | None, typer.Option("--context", help="Kubernetes context (default: current).")
    ] = None,
    namespace: Annotated[
        str, typer.Option("--namespace", "-n", help="Namespace of the run index.")
    ] = CONST_RUNS_INDEX_NAMESPACE,
    service: Annotated[
        str, typer.Option("--service", help="Service of the run index's Valkey.")
    ] = CONST_RUNS_INDEX_SERVICE,
    secret: Annotated[
        str, typer.Option("--secret", help="Secret holding the Valkey password.")
    ] = CONST_RUNS_INDEX_SECRET,
) -> None:
    """Find the cluster's run index, check it answers, share runs through it, and index them."""
    from devops_cli.config.settings import dotted_set, load_settings, save_settings

    try:
        host, port = node_port_address(context, namespace, service, RUNS_INDEX)
        password = secret_value(context, namespace, secret, "password")
    except ServiceNotReachableError as exc:
        print_error(f"Cannot find the run index: {exc.message}", prefix=False)
        raise typer.Exit(code=1) from exc
    url = f"valkey://{host}:{port}"
    records = load_runs()
    try:
        with RunIndex.connect(url, password) as index:
            count = index.put(*records) if records else 0
    except ValkeyError as exc:
        print_error(f"The run index at {host}:{port} does not answer: {mask_secrets(exc.message)}")
        raise typer.Exit(code=1) from exc
    settings = load_settings()
    dotted_set(settings, opt.RUNS_INDEX_PASSWORD, password)
    settings.runs.index_url = url
    save_settings(settings)
    print_success(
        f"Runs are shared through the run index at {host}:{port}; indexed {count} run(s)."
    )


def _render_runs_table(records: list[RunRecord]) -> None:
    """Format and print a table of historical benchmark/evaluation runs."""
    rows = [
        [
            r.run_id,
            r.mechanism.value,
            r.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            r.commit or "—",
            r.fingerprint[:8],
            r.subject_key[:8],
        ]
        for r in records
    ]
    print_table(
        title="Benchmark & Evaluation Runs",
        columns=[
            ("Run ID", "cyan"),
            ("Mechanism", "magenta"),
            ("Created", "green"),
            ("Commit", "yellow"),
            ("Fingerprint", "dim"),
            ("Subject", "white"),
        ],
        rows=rows,
    )


def _render_run_details(record: RunRecord) -> None:
    """Format and print full metadata and results for a run record."""
    print_section(f" Run: {record.run_id} ", style="bold cyan")
    meta_rows = [
        ["Run ID", record.run_id],
        ["Mechanism", record.mechanism.value],
        ["Created At", record.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")],
        ["Version", record.version],
        ["Commit", record.commit or "—"],
        ["Setup Fingerprint", record.fingerprint],
        ["Subject Key", record.subject_key],
    ]
    print_table(
        title="Run Metadata", columns=[("Field", "cyan"), ("Value", "white")], rows=meta_rows
    )

    if record.setup:
        setup_rows = [[k, json.dumps(v, default=str)] for k, v in sorted(record.setup.items())]
        print_table(
            title="Setup Parameters",
            columns=[("Parameter", "cyan"), ("Value", "yellow")],
            rows=setup_rows,
        )

    if record.subject:
        subj_rows = [[k, json.dumps(v, default=str)] for k, v in sorted(record.subject.items())]
        print_table(
            title="Subject Details", columns=[("Key", "cyan"), ("Value", "white")], rows=subj_rows
        )

    if record.results:
        res_rows = [
            [k, json.dumps(v, default=str)]
            for k, v in sorted(record.results.items())
            if not isinstance(v, (dict, list))
        ]
        if res_rows:
            print_table(
                title="Run Summary Results",
                columns=[("Metric", "cyan"), ("Value", "green")],
                rows=res_rows,
            )


def _render_setup_diff(diff: dict[str, tuple[Any, Any]]) -> None:
    """Render setup parameter differences between runs."""
    if not diff:
        print_info("✓ Setup configurations are identical.")
        return
    rows = [
        [k, json.dumps(v[0], default=str), json.dumps(v[1], default=str)]
        for k, v in sorted(diff.items())
    ]
    print_table(
        title="Setup Differences",
        columns=[("Setting", "cyan"), ("Base Run", "white"), ("Current Run", "yellow")],
        rows=rows,
    )


def _render_comparison_metrics(metrics: dict[str, MetricDiff]) -> None:
    """Render numeric metric differences."""
    rows = []
    for m in sorted(metrics.values(), key=lambda item: item.name):
        change_str = f"{m.absolute_change:+g}"
        pct_str = f"{m.percent_change:+.1f}%" if m.percent_change is not None else "—"
        rows.append([m.name, f"{m.base_value:.4g}", f"{m.current_value:.4g}", change_str, pct_str])
    print_table(
        title="Metrics Comparison",
        columns=[
            ("Metric", "cyan"),
            ("Base", "right"),
            ("Current", "right"),
            ("Change", "right"),
            ("% Change", "right"),
        ],
        rows=rows,
    )


def _render_backend_shares(shares: dict[str, MetricDiff]) -> None:
    """Render backend activity differences."""
    rows = []
    for b in sorted(shares.values(), key=lambda item: item.name):
        change_str = f"{b.absolute_change:+.1%}"
        rows.append([b.name, f"{b.base_value:.1%}", f"{b.current_value:.1%}", change_str])
    print_table(
        title="Backend Busy Share Comparison",
        columns=[
            ("Backend", "cyan"),
            ("Base Share", "right"),
            ("Current Share", "right"),
            ("Change", "right"),
        ],
        rows=rows,
    )


def _render_comparison(comparison: RunComparison) -> None:
    """Render comprehensive comparison between two runs."""
    print_section(
        f" Comparison: {comparison.base_run.run_id} → {comparison.current_run.run_id} ",
        style="bold cyan",
    )
    if comparison.same_fingerprint:
        print_info(
            f"✓ Matching setup fingerprint: [dim]{comparison.base_run.fingerprint[:8]}[/dim]"
        )
    else:
        print_warning(
            f"⚠ Setup differed: {comparison.base_run.fingerprint[:8]} → {comparison.current_run.fingerprint[:8]}"
        )
        _render_setup_diff(comparison.setup_diff)

    if comparison.metrics:
        _render_comparison_metrics(comparison.metrics)
    if comparison.backend_shares:
        _render_backend_shares(comparison.backend_shares)


def _render_baselines_table(baselines: list[BaselineRecord]) -> None:
    """Render table of designated subject baselines."""
    rows = [
        [
            b.mechanism.value,
            b.subject_key[:8],
            b.run_id,
            b.set_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
        ]
        for b in baselines
    ]
    print_table(
        title="Designated Subject Baselines",
        columns=[
            ("Mechanism", "magenta"),
            ("Subject Key", "cyan"),
            ("Baseline Run ID", "green"),
            ("Designated At", "white"),
        ],
        rows=rows,
    )


def _render_regression_report(report: RegressionReport) -> None:
    """Render regression check evaluation table."""
    rows = []
    for v in report.verdicts:
        change_str = f"{v.change_pct:+.1f}%" if v.change_pct is not None else "—"
        verdict_str = "[green]✓ Pass[/green]" if v.passed else "[red]✗ Fail[/red]"
        rows.append(
            [
                v.metric,
                f"{v.base_value:.4g}",
                f"{v.current_value:.4g}",
                change_str,
                f"{v.tolerance_pct:.1f}%",
                verdict_str,
            ]
        )
    print_table(
        title="Regression Check Results",
        columns=[
            ("Metric", "cyan"),
            ("Base", "right"),
            ("Current", "right"),
            ("Change", "right"),
            ("Tolerance", "right"),
            ("Verdict", "bold"),
        ],
        rows=rows,
    )


@app.command("list")
@trace_span("ai.runs.list")
def list_cmd(
    mechanism: Annotated[
        Mechanism | None,
        typer.Option("--mechanism", "-m", help="Only list runs of this mechanism."),
    ] = None,
    subject_key: Annotated[
        str | None,
        typer.Option(
            "--subject-key", "-s", help="Only list runs matching this subject key or prefix."
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Maximum number of runs to show."),
    ] = 20,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format: table or json."),
    ] = "table",
) -> None:
    """List recorded benchmark and evaluation runs."""
    records = load_runs(mechanism)
    if subject_key:
        records = [
            r
            for r in records
            if r.subject_key == subject_key or r.subject_key.startswith(subject_key)
        ]
    records = sorted(records, key=lambda r: (r.created_at, r.run_id), reverse=True)[:limit]

    resolved = normalize_format(output_format)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized([r.model_dump(mode="json") for r in records], resolved)
        return

    if not records:
        print_info(f"No runs found matching criteria in {escape_text(str(runs_dir()))}.")
        return

    _render_runs_table(records)


@app.command("show")
@trace_span("ai.runs.show")
def show_cmd(
    run_id: Annotated[str, typer.Argument(help="Run ID or prefix to show.")],
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format: table or json."),
    ] = "table",
) -> None:
    """Show details of a recorded run."""
    record = get_run(run_id)
    if record is None:
        print_error(f"Run {escape_text(run_id)} not found.")
        raise typer.Exit(code=1)

    resolved = normalize_format(output_format)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized(record.model_dump(mode="json"), resolved)
        return

    _render_run_details(record)


@app.command("compare")
@trace_span("ai.runs.compare")
def compare_cmd(
    run_a: Annotated[
        str,
        typer.Argument(help="First run ID (or current run if second run is omitted)."),
    ],
    run_b: Annotated[
        str | None,
        typer.Argument(help="Second run ID (optional; defaults to subject baseline)."),
    ] = None,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format: table or json."),
    ] = "table",
) -> None:
    """Compare two runs or a run against its subject's baseline."""
    rec_a = get_run(run_a)
    if rec_a is None:
        print_error(f"Run {escape_text(run_a)} not found.")
        raise typer.Exit(code=1)

    if run_b is not None:
        rec_b = get_run(run_b)
        if rec_b is None:
            print_error(f"Run {escape_text(run_b)} not found.")
            raise typer.Exit(code=1)
        base, current = rec_a, rec_b
    else:
        baseline = get_baseline(rec_a.mechanism, rec_a.subject_key)
        if baseline is None:
            print_error(
                f"No baseline is configured for {rec_a.mechanism.value} subject {rec_a.subject_key[:8]}; "
                f"set one with: devops ai runs baseline set {rec_a.run_id}"
            )
            raise typer.Exit(code=1)
        base, current = baseline, rec_a

    comparison = compare_runs(base, current)
    resolved = normalize_format(output_format)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized(comparison.model_dump(mode="json"), resolved)
        return

    _render_comparison(comparison)


baseline_app = new_typer(help=HELP.ai.runs_baseline, no_args_is_help=True)
app.add_typer(baseline_app, name="baseline")


@baseline_app.command("set")
@trace_span("ai.runs.baseline.set")
def baseline_set_cmd(
    run_id: Annotated[str, typer.Argument(help="Run ID to designate as baseline.")],
) -> None:
    """Set a run as the baseline for its subject."""
    record = get_run(run_id)
    if record is None:
        print_error(f"Run {escape_text(run_id)} not found.")
        raise typer.Exit(code=1)
    b_record = set_baseline(record)
    print_success(
        f"Designated run {escape_text(record.run_id)} as baseline for "
        f"{record.mechanism.value} subject {b_record.subject_key[:8]}."
    )


@baseline_app.command("list")
@trace_span("ai.runs.baseline.list")
def baseline_list_cmd(
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format: table or json."),
    ] = "table",
) -> None:
    """List all configured baselines."""
    baselines = list_baselines()
    resolved = normalize_format(output_format)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized([b.model_dump(mode="json") for b in baselines], resolved)
        return
    if not baselines:
        print_info("No baselines configured. Set one with: devops ai runs baseline set <run-id>")
        return
    _render_baselines_table(baselines)


def _find_baseline_run(subject_or_run: str, mechanism: Mechanism | None) -> RunRecord | None:
    """Find a baseline record by subject key or run ID, with or without mechanism."""
    run = get_run(subject_or_run)
    mech = mechanism or (run.mechanism if run else None)
    subj_key = run.subject_key if run else subject_or_run
    if mech:
        return get_baseline(mech, subj_key)
    for m in Mechanism:
        found = get_baseline(m, subj_key)
        if found is not None:
            return found
    return None


@baseline_app.command("show")
@trace_span("ai.runs.baseline.show")
def baseline_show_cmd(
    subject_or_run: Annotated[
        str,
        typer.Argument(help="Subject key or run ID to inspect baseline for."),
    ],
    mechanism: Annotated[
        Mechanism | None,
        typer.Option("--mechanism", "-m", help="Mechanism for subject lookup."),
    ] = None,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format: table or json."),
    ] = "table",
) -> None:
    """Show the baseline for a subject or run."""
    baseline_run = _find_baseline_run(subject_or_run, mechanism)
    if baseline_run is None:
        print_error(f"No baseline found for {escape_text(subject_or_run)}.")
        raise typer.Exit(code=1)

    resolved = normalize_format(output_format)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized(baseline_run.model_dump(mode="json"), resolved)
        return

    _render_run_details(baseline_run)


@app.command("check")
@trace_span("ai.runs.check")
def check_cmd(
    run_id: Annotated[str, typer.Argument(help="Run ID to check against baseline.")],
    baseline_id: Annotated[
        str | None,
        typer.Option("--baseline", "-b", help="Override baseline run ID to compare against."),
    ] = None,
    max_recall_drop: Annotated[
        float,
        typer.Option(
            "--max-recall-drop",
            help="Maximum allowable relative drop in recall (e.g. 0.05 for 5%).",
        ),
    ] = 0.0,
    max_duration_increase: Annotated[
        float,
        typer.Option(
            "--max-duration-increase",
            help="Maximum allowable relative increase in duration (e.g. 0.15 for 15%).",
        ),
    ] = 0.15,
    max_tokens_increase: Annotated[
        float,
        typer.Option(
            "--max-tokens-increase",
            help="Maximum allowable relative increase in prompt tokens (e.g. 0.20 for 20%).",
        ),
    ] = 0.20,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format: table or json."),
    ] = "table",
) -> None:
    """Check a run against baseline for regressions past tolerances."""
    record = get_run(run_id)
    if record is None:
        print_error(f"Run {escape_text(run_id)} not found.")
        raise typer.Exit(code=1)

    if baseline_id:
        base_record = get_run(baseline_id)
        if base_record is None:
            print_error(f"Baseline run {escape_text(baseline_id)} not found.")
            raise typer.Exit(code=1)
    else:
        base_record = get_baseline(record.mechanism, record.subject_key)
        if base_record is None:
            print_error(
                f"No baseline is configured for {record.mechanism.value} subject {record.subject_key[:8]}; "
                f"set one with: devops ai runs baseline set {record.run_id}"
            )
            raise typer.Exit(code=1)

    tolerances = RegressionTolerances(
        max_recall_drop=max_recall_drop,
        max_duration_increase=max_duration_increase,
        max_tokens_increase=max_tokens_increase,
    )
    comparison = compare_runs(base_record, record)
    report = check_regression(comparison, tolerances)

    resolved = normalize_format(output_format)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized(report.model_dump(mode="json"), resolved)
        if not report.passed:
            raise typer.Exit(code=1)
        return

    _render_regression_report(report)
    if not report.passed:
        print_error(
            "Regression check failed: one or more metrics regressed past allowed tolerance."
        )
        raise typer.Exit(code=1)
    print_success(
        f"Run {escape_text(record.run_id)} passed all regression checks against baseline."
    )
