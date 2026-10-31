"""CLI commands for tracking lifetime AI/LLM request spend and managing model pricing."""

from __future__ import annotations

from typing import Annotated

import typer
import yaml

from devops_cli.ai.spend import get_pricing_registry, get_spend_ledger
from devops_cli.ai.spend.models import HardwarePayoffSummary, LifetimeSpendReport
from devops_cli.config.constants import CONST_AI_BACKEND_HOST_UNKNOWN
from devops_cli.core.cli import new_typer
from devops_cli.dry_run import dry_run_class, is_dry_run
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import (
    format_json,
    format_yaml,
    print_error,
    print_info,
    print_success,
    print_table,
    print_warning,
    write_stdout,
)

app = new_typer(
    help="Track approximate lifetime spend and manage open-source model pricing.",
    no_args_is_help=False,
)


def _usd(value: float | None, unit: str = "") -> str:
    """A hosted cost equivalent as dollars, or `unpriced` when its reference model has no price
    (#1672)."""
    return MESSAGES.ai.savings_unpriced if value is None else f"${value:,.4f}{unit}"


def _render_report_summary_table(report: LifetimeSpendReport) -> None:
    """Render high-level spend and token overview table."""
    references = f"{report.reference_model}, embeddings at {report.reference_embedding_model}"
    rows: list[list[str]] = [
        ["Total Approximate Spend", f"${report.total_spend_usd:,.4f} USD"],
        ["Total Requests Processed", f"{report.total_requests:,}"],
        ["Total Prompt (Input) Tokens", f"{report.total_prompt_tokens:,}"],
        ["Total Completion (Output) Tokens", f"{report.total_completion_tokens:,}"],
        ["Total Reasoning Tokens", f"{report.total_reasoning_tokens:,}"],
        ["Total Tokens", f"{report.total_tokens:,}"],
        ["Cached Requests (Saved Spend)", f"{report.cached_requests:,}"],
        ["Active Backend Servers", str(report.active_servers_count)],
        ["Active Models Evaluated", str(report.active_models_count)],
        [
            "Local Calls Hosted Equivalent",
            f"{_usd(report.local_cost_equivalent_usd, ' USD')} ({references})",
        ],
        [
            "All-Hosted Counterfactual Spend",
            f"{_usd(report.counterfactual_spend_usd, ' USD')} ({references})",
        ],
        ["Estimated Cloud Spend Avoided", _usd(report.counterfactual_savings_usd, " USD")],
    ]
    if report.first_recorded_at:
        rows.append(["First Recorded Request", str(report.first_recorded_at)])
    if report.last_recorded_at:
        rows.append(["Latest Recorded Request", str(report.last_recorded_at)])

    print_table(
        title="Lifetime AI Spend & Token Overview",
        columns=[("Metric", "cyan"), ("Value", "bold green")],
        rows=rows,
    )


def _render_hardware_payoff_table(payoff: HardwarePayoffSummary) -> None:
    """Render hardware purchase payoff and local LLM savings overview table."""
    if payoff.hardware_cost_usd <= 0:
        est_days_str = "N/A (hardware cost unset)"
    elif payoff.is_paid_off:
        est_days_str = "Fully Paid Off"
    elif payoff.estimated_days_to_payoff is not None:
        est_days_str = f"{payoff.estimated_days_to_payoff:.1f} days"
    else:
        est_days_str = "Insufficient activity"
    status_str = (
        f"Fully Paid Off! (+{payoff.payoff_percentage - 100.0:.1f}% net ROI)"
        if payoff.is_paid_off
        else (
            f"Amortizing ({payoff.payoff_percentage:.1f}% paid off)"
            if payoff.hardware_cost_usd > 0
            else "Tracking local savings (hardware cost unset)"
        )
    )
    net_str = (
        f"+${payoff.net_value_usd:,.4f} USD"
        if payoff.net_value_usd >= 0
        else f"-${abs(payoff.net_value_usd):,.4f} USD"
    )
    rows: list[list[str]] = [
        ["Total Hardware Investment", f"${payoff.hardware_cost_usd:,.2f} USD"],
        [
            "Local Hardware Savings Generated",
            f"${payoff.cumulative_savings_usd:,.4f} USD (vs. {payoff.reference_model})",
        ],
        ["Investment Pay-off Progress", f"{payoff.payoff_percentage:.2f}%"],
        ["Net Value Created", net_str],
        ["Remaining to Break-Even", f"${payoff.remaining_usd:,.2f} USD"],
        ["Average Daily Savings Run-Rate", f"${payoff.daily_savings_usd:,.4f} USD/day"],
        ["Estimated Days to Break-Even", est_days_str],
        ["Payoff Status", status_str],
    ]
    print_table(
        title="Local Hardware Investment & Cloud Savings Pay-Off",
        columns=[("Metric", "cyan"), ("Value", "bold green")],
        rows=rows,
    )


def _render_servers_table(report: LifetimeSpendReport) -> None:
    """Render spend breakdown by backend service/server."""
    if not report.servers:
        print_info("No backend server spend records found.")
        return

    cols = [
        ("Backend Server Endpoint", "cyan"),
        ("Provider", "yellow"),
        ("Requests", "blue"),
        ("In Tokens", "magenta"),
        ("Out Tokens", "magenta"),
        ("Reasoning Share", "magenta"),
        ("Total Tokens", "magenta"),
        ("Approx Spend (USD)", "bold green"),
        ("Hosted Equiv (USD)", "green"),
    ]
    rows: list[list[str]] = [
        [
            s.server,
            s.provider,
            f"{s.request_count:,}",
            f"{s.prompt_tokens:,}",
            f"{s.completion_tokens:,}",
            f"{(s.reasoning_tokens / s.completion_tokens) * 100:.1f}%"
            if s.completion_tokens > 0
            else "0.0%",
            f"{s.total_tokens:,}",
            f"${s.approx_spend_usd:,.4f}",
            _usd(s.cost_equivalent_usd),
        ]
        for s in report.servers
    ]
    print_table(title="AI Spend & Usage by Backend Service / Server", columns=cols, rows=rows)


def _render_models_table(report: LifetimeSpendReport) -> None:
    """Render spend breakdown by model identifier."""
    if not report.models:
        print_info("No model spend records found.")
        return

    cols = [
        ("Model", "cyan"),
        ("Provider", "yellow"),
        ("Requests", "blue"),
        ("Total Tokens", "magenta"),
        ("Reasoning Share", "magenta"),
        ("Approx Spend (USD)", "bold green"),
        ("Hosted Equiv (USD)", "green"),
    ]
    rows: list[list[str]] = [
        [
            m.model,
            m.provider,
            f"{m.request_count:,}",
            f"{m.total_tokens:,}",
            f"{(m.reasoning_tokens / m.completion_tokens) * 100:.1f}%"
            if m.completion_tokens > 0
            else "0.0%",
            f"${m.approx_spend_usd:,.4f}",
            _usd(m.cost_equivalent_usd),
        ]
        for m in report.models
    ]
    print_table(title="AI Spend & Usage by Model", columns=cols, rows=rows)


def _render_providers_table(report: LifetimeSpendReport) -> None:
    """Render spend breakdown by provider category."""
    if not report.providers:
        print_info("No provider spend records found.")
        return

    cols = [
        ("Provider", "cyan"),
        ("Servers", "yellow"),
        ("Requests", "blue"),
        ("Total Tokens", "magenta"),
        ("Approx Spend (USD)", "bold green"),
    ]
    rows: list[list[str]] = [
        [
            p.provider,
            str(p.server_count),
            f"{p.request_count:,}",
            f"{p.total_tokens:,}",
            f"${p.approx_spend_usd:,.4f}",
        ]
        for p in report.providers
    ]
    print_table(title="AI Spend & Usage by Provider", columns=cols, rows=rows)


def _served_by_label(served_by: str) -> str:
    """The `host[:port]` of a stored serving backend, never its userinfo; `unknown` when the
    value names no server."""
    from devops_cli.ai.client.models import served_by_authority

    authority = served_by_authority(served_by)
    return authority.label if authority is not None else CONST_AI_BACKEND_HOST_UNKNOWN


def _render_backends_table(report: LifetimeSpendReport) -> None:
    """Render gateway calls by the backend that served them."""
    if not report.backends:
        print_info("No gateway calls with a recorded serving backend.")
        return

    cols = [
        ("Serving Backend", "cyan"),
        ("Models", "yellow"),
        ("Requests", "blue"),
        ("In Tokens", "magenta"),
        ("Out Tokens", "magenta"),
        ("Out Tokens / Request", "magenta"),
        ("Reasoning Share", "magenta"),
        ("Mean Seconds", "bold green"),
    ]
    rows: list[list[str]] = [
        [
            _served_by_label(b.served_by),
            ", ".join(b.models),
            f"{b.request_count:,}",
            f"{b.prompt_tokens:,}",
            f"{b.completion_tokens:,}",
            f"{b.completion_tokens_per_request:,.1f}",
            f"{(b.reasoning_tokens / b.completion_tokens) * 100:.1f}%"
            if b.completion_tokens > 0
            else "0.0%",
            f"{b.mean_duration_seconds:,.2f}",
        ]
        for b in report.backends
    ]
    print_table(title="Gateway Calls by Serving Backend", columns=cols, rows=rows)


def _render_stages_table(report: LifetimeSpendReport) -> None:
    """Render spend breakdown by execution stage."""
    if not report.stages:
        print_info("No stage spend records found.")
        return

    cols = [
        ("Stage", "cyan"),
        ("Calls", "blue"),
        ("Tokens", "magenta"),
        ("Cost (USD)", "bold green"),
        ("Hosted Equiv (USD)", "green"),
    ]
    rows: list[list[str]] = [
        [
            s.stage,
            f"{s.request_count:,}",
            f"{s.total_tokens:,}",
            f"${s.approx_spend_usd:,.4f}",
            _usd(s.cost_equivalent_usd),
        ]
        for s in report.stages
    ]
    print_table(title="AI Spend & Usage by Execution Stage", columns=cols, rows=rows)


def _render_report_tables(report: LifetimeSpendReport, by: str) -> None:
    """Dispatch table rendering based on grouping selection."""
    _render_report_summary_table(report)
    if report.hardware_payoff and (
        report.hardware_cost_usd > 0 or (report.local_cost_equivalent_usd or 0.0) > 0
    ):
        _render_hardware_payoff_table(report.hardware_payoff)
    if by in ("server", "all"):
        _render_servers_table(report)
    if by in ("model", "all"):
        _render_models_table(report)
    if by in ("provider", "all"):
        _render_providers_table(report)
    if by in ("backend", "all"):
        _render_backends_table(report)
    if by in ("stage", "all"):
        _render_stages_table(report)


@app.callback(invoke_without_command=True)
@dry_run_class("no-external-request")
def cost_default(
    ctx: typer.Context,
    by: Annotated[
        str,
        typer.Option(
            "--by",
            "-b",
            help="Breakdown grouping dimension: server, model, provider, backend, stage, all.",
        ),
    ] = "server",
    days: Annotated[
        int | None,
        typer.Option(
            "--days",
            "-d",
            help="Filter usage to the last N days (default: all lifetime).",
        ),
    ] = None,
    reference_model: Annotated[
        str | None,
        typer.Option(
            "--reference-model",
            "-m",
            help="Reference model for counterfactual pricing (default: the ai.reference_model setting).",
        ),
    ] = None,
    hardware_cost: Annotated[
        float | None,
        typer.Option(
            "--hardware-cost",
            "-H",
            help="Hardware purchase cost in USD to track pay-off against.",
        ),
    ] = None,
    format_opt: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="Output format: table, json, yaml, markdown.",
        ),
    ] = "table",
    json_flag: Annotated[
        bool,
        typer.Option(
            "--json",
            help="First-class alias for --format json.",
        ),
    ] = False,
) -> None:
    """Report approximate AI spend and token usage across lifetime of DevOps CLI use."""
    if ctx.invoked_subcommand is not None:
        return

    eff_format = "json" if json_flag else format_opt.lower()
    ledger = get_spend_ledger()
    report = ledger.get_lifetime_report(
        days=days,
        group_by=by,
        reference_model=reference_model,
        hardware_cost_usd=hardware_cost,
    )

    if eff_format == "json":
        write_stdout(format_json(report.model_dump()))
        return
    if eff_format == "yaml":
        write_stdout(yaml.dump(report.model_dump(), sort_keys=False))
        return
    if eff_format in ("prometheus", "prom"):
        from devops_cli.ai.spend import export_ai_spend_prometheus

        write_stdout(export_ai_spend_prometheus(ledger, report=report))
        return

    _render_report_tables(report, by)


@app.command(name="report")
@dry_run_class("no-external-request")
def cost_report(
    by: Annotated[
        str,
        typer.Option(
            "--by",
            "-b",
            help="Breakdown grouping dimension: server, model, provider, backend, stage, all.",
        ),
    ] = "server",
    days: Annotated[
        int | None,
        typer.Option(
            "--days",
            "-d",
            help="Filter usage to the last N days (default: all lifetime).",
        ),
    ] = None,
    reference_model: Annotated[
        str | None,
        typer.Option(
            "--reference-model",
            "-m",
            help="Reference model for counterfactual pricing (default: the ai.reference_model setting).",
        ),
    ] = None,
    hardware_cost: Annotated[
        float | None,
        typer.Option(
            "--hardware-cost",
            "-H",
            help="Hardware purchase cost in USD to track pay-off against.",
        ),
    ] = None,
    format_opt: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="Output format: table, json, yaml, prometheus.",
        ),
    ] = "table",
    json_flag: Annotated[
        bool,
        typer.Option(
            "--json",
            help="First-class alias for --format json.",
        ),
    ] = False,
) -> None:
    """Generate detailed spend and token report across backend services and servers."""
    eff_format = "json" if json_flag else format_opt.lower()
    ledger = get_spend_ledger()
    report = ledger.get_lifetime_report(
        days=days,
        group_by=by,
        reference_model=reference_model,
        hardware_cost_usd=hardware_cost,
    )

    if eff_format == "json":
        write_stdout(format_json(report.model_dump()))
        return
    if eff_format == "yaml":
        write_stdout(yaml.dump(report.model_dump(), sort_keys=False))
        return
    if eff_format in ("prometheus", "prom"):
        from devops_cli.ai.spend import export_ai_spend_prometheus

        write_stdout(export_ai_spend_prometheus(ledger, report=report))
        return

    _render_report_tables(report, by)


@app.command(name="roi")
@dry_run_class("no-external-request")
def cost_roi(
    hardware_cost: Annotated[
        float | None,
        typer.Option(
            "--hardware-cost",
            "-H",
            help="Total hardware purchase cost in USD (e.g. 1599.0 for GPU/workstation).",
        ),
    ] = None,
    reference_model: Annotated[
        str | None,
        typer.Option(
            "--reference-model",
            "-m",
            help="Reference model for counterfactual pricing (default: the ai.reference_model setting).",
        ),
    ] = None,
    days: Annotated[
        int | None,
        typer.Option(
            "--days",
            "-d",
            help="Filter usage to the last N days (default: all lifetime).",
        ),
    ] = None,
    format_opt: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="Output format: table, json, yaml.",
        ),
    ] = "table",
    json_flag: Annotated[
        bool,
        typer.Option(
            "--json",
            help="First-class alias for --format json.",
        ),
    ] = False,
) -> None:
    """Monitor pay-off in value for local hardware purchases and local LLM savings."""
    eff_format = "json" if json_flag else format_opt.lower()
    ledger = get_spend_ledger()
    report = ledger.get_lifetime_report(
        days=days,
        group_by="all",
        reference_model=reference_model,
        hardware_cost_usd=hardware_cost,
    )

    if eff_format == "json":
        data = report.hardware_payoff.model_dump() if report.hardware_payoff else {}
        write_stdout(format_json(data))
        return
    if eff_format == "yaml":
        data = report.hardware_payoff.model_dump() if report.hardware_payoff else {}
        write_stdout(yaml.dump(data, sort_keys=False))
        return

    if report.hardware_payoff:
        _render_hardware_payoff_table(report.hardware_payoff)
    elif report.local_cost_equivalent_usd is None:
        print_warning(
            MESSAGES.ai.payoff_unpriced.format(models=", ".join(report.unpriced_reference_models))
        )
    else:
        print_info("No local LLM inference records found to calculate hardware payoff.")


@app.command(name="payoff", hidden=True)
@dry_run_class("no-external-request")
def cost_payoff(
    hardware_cost: Annotated[
        float | None,
        typer.Option("--hardware-cost", "-H"),
    ] = None,
    reference_model: Annotated[
        str | None,
        typer.Option("--reference-model", "-m"),
    ] = None,
    days: Annotated[
        int | None,
        typer.Option("--days", "-d"),
    ] = None,
    format_opt: Annotated[
        str,
        typer.Option("--format", "-f"),
    ] = "table",
    json_flag: Annotated[
        bool,
        typer.Option("--json"),
    ] = False,
) -> None:
    """Alias for 'roi' command."""
    cost_roi(
        hardware_cost=hardware_cost,
        reference_model=reference_model,
        days=days,
        format_opt=format_opt,
        json_flag=json_flag,
    )


@app.command(name="payback", hidden=True)
@dry_run_class("no-external-request")
def cost_payback(
    hardware_cost: Annotated[
        float | None,
        typer.Option("--hardware-cost", "-H"),
    ] = None,
    reference_model: Annotated[
        str | None,
        typer.Option("--reference-model", "-m"),
    ] = None,
    days: Annotated[
        int | None,
        typer.Option("--days", "-d"),
    ] = None,
    format_opt: Annotated[
        str,
        typer.Option("--format", "-f"),
    ] = "table",
    json_flag: Annotated[
        bool,
        typer.Option("--json"),
    ] = False,
) -> None:
    """Alias for 'roi' command."""
    cost_roi(
        hardware_cost=hardware_cost,
        reference_model=reference_model,
        days=days,
        format_opt=format_opt,
        json_flag=json_flag,
    )


@app.command(name="prometheus")
@dry_run_class("no-external-request")
def cost_prometheus() -> None:
    """Export the totals of the spend ledger as Prometheus gauges."""
    from devops_cli.ai.spend import export_ai_spend_prometheus

    ledger = get_spend_ledger()
    write_stdout(export_ai_spend_prometheus(ledger))


@app.command(name="update-pricing")
@dry_run_class("request-plan")
def cost_update_pricing(
    source: Annotated[
        str | None,
        typer.Option(
            "--source",
            "-s",
            help="Custom URL or file path for open-source model pricing dataset.",
        ),
    ] = None,
    reset: Annotated[
        bool,
        typer.Option(
            "--reset",
            help="Reset custom pricing snapshot and restore bundled catalog.",
        ),
    ] = False,
    timeout: Annotated[
        float,
        typer.Option(
            "--timeout",
            "-t",
            help="Request timeout in seconds.",
        ),
    ] = 15.0,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Synchronize open-source industrial average pricing catalog from remote registry."""
    if reset and source:
        raise typer.BadParameter("Cannot combine --reset with --source.")

    if dry_run or is_dry_run():
        from devops_cli.ai.ai_plans import plan_ai_cost_update_pricing
        from devops_cli.dry_run import render_request_plan

        plan = plan_ai_cost_update_pricing(source=source, reset=reset, timeout=timeout)
        render_request_plan("Plan for AI cost update-pricing", plan)
        return

    registry = get_pricing_registry()
    if reset:
        registry.reset_pricing()
        print_success("Successfully reset pricing snapshot to bundled dataset.")
        return

    try:
        res = registry.update_from_remote(source_url=source, timeout=timeout)
        if isinstance(res, tuple):
            source_count, merged_count = res[0], res[1]
        else:
            source_count = merged_count = int(res)
        print_success(
            f"Successfully synchronized open-source pricing catalog: {source_count:,} models supplied, {merged_count:,} models in merged catalog."
        )
    except Exception as exc:
        print_error(f"Failed to update pricing catalog: {exc}")
        raise typer.Exit(code=1) from exc


@app.command(name="list-pricing")
@dry_run_class("no-external-request")
def cost_list_pricing(
    search: Annotated[
        str | None,
        typer.Option(
            "--search",
            "-s",
            help="Substring or pattern filter for model/endpoint names.",
        ),
    ] = None,
    format_opt: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="Output format: table, json, yaml.",
        ),
    ] = "table",
    json_flag: Annotated[
        bool,
        typer.Option(
            "--json",
            help="First-class alias for --format json.",
        ),
    ] = False,
) -> None:
    """List active token pricing rates per model and backend server.

    Rates are base-tier rates for a small call at the current time; each call is priced from its own usage and request time.
    """
    eff_format = "json" if json_flag else format_opt.lower()
    registry = get_pricing_registry()
    all_prices = registry.list_all_pricing()

    filtered = {
        k: v
        for k, v in all_prices.items()
        if not search or search.lower() in k or (v.source and search.lower() in v.source)
    }

    if eff_format == "json":
        data = {k: v.model_dump() for k, v in filtered.items()}
        write_stdout(format_json(data))
        return
    if eff_format == "yaml":
        data = {k: v.model_dump() for k, v in filtered.items()}
        write_stdout(format_yaml(data))
        return

    cols = [
        ("Model / Target Endpoint", "cyan"),
        ("Base Prompt USD / 1M", "magenta"),
        ("Base Completion USD / 1M", "magenta"),
        ("Pricing Source", "yellow"),
    ]
    rows: list[list[str]] = [
        [
            k,
            f"${v.prompt_usd_per_million:.4f}",
            f"${v.completion_usd_per_million:.4f}",
            v.source,
        ]
        for k, v in sorted(filtered.items())
    ]
    caption = "Rates are base-tier rates for a small call at current time; each call is priced from its own usage and request time."
    print_table(
        title=f"AI Model Pricing Catalog ({len(filtered):,} entries)",
        columns=cols,
        rows=rows,
        caption=caption,
    )


@app.command(name="set-price")
@dry_run_class("no-external-request")
def cost_set_price(
    target: Annotated[
        str,
        typer.Argument(
            help="Target model identifier or backend server address of hosted calls (e.g. 'gpt-4o', 'api.example.com'). When a gateway reply names its deployment model, such as 'openai/gpt-4o', that model is the target, not the route name. A local call costs nothing, also when it has a custom price. Its tokens count in local savings.",
        ),
    ],
    prompt_rate: Annotated[
        float,
        typer.Argument(
            help="Prompt token cost in USD per 1,000,000 tokens.",
        ),
    ],
    completion_rate: Annotated[
        float,
        typer.Argument(
            help="Completion token cost in USD per 1,000,000 tokens.",
        ),
    ],
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Set a custom token price for the hosted calls of a model or backend server."""
    if dry_run or is_dry_run():
        print_info(
            f"Dry run: Would configure custom pricing for '{target}': "
            f"${prompt_rate:.4f} prompt / ${completion_rate:.4f} completion per 1M tokens."
        )
        return

    registry = get_pricing_registry()
    p = registry.set_custom_pricing(target, prompt_rate, completion_rate)
    print_success(
        f"Configured custom pricing for '{target}': "
        f"${p.prompt_usd_per_million:.4f} prompt / ${p.completion_usd_per_million:.4f} completion per 1M tokens."
    )


@app.command(name="reset")
@dry_run_class("no-external-request")
def cost_reset(
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            "-y",
            help="Confirm deletion of lifetime spend ledger records.",
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Reset the lifetime AI spend ledger records."""
    if dry_run or is_dry_run():
        print_info("Dry run: Would reset lifetime AI spend ledger records (0 records cleared).")
        return

    if not yes:
        confirm = typer.confirm(
            "Are you sure you want to reset all lifetime AI spend and token usage records?"
        )
        if not confirm:
            print_info("Spend ledger reset aborted.")
            return

    ledger = get_spend_ledger()
    count = ledger.reset_ledger()
    print_success(f"Successfully reset lifetime spend ledger: {count:,} records cleared.")
