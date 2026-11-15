"""CLI command implementation for devops ai agent-audit (#2346)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Annotated

import typer

from devops_cli.ai.agent_audit.filing import drafts_of, file_drafts
from devops_cli.ai.agent_audit.finding import Finding, build_findings, rank_findings
from devops_cli.ai.agent_audit.grouping import group_findings, groups_of
from devops_cli.ai.agent_audit.report import render_report
from devops_cli.ai.agent_audit.sources import read_sources, resolve_sources
from devops_cli.ai.agent_audit.store import merge_counts, store_path
from devops_cli.ai.agent_audit.tracked import GitHubTrackedIssues, mark_tracked
from devops_cli.dry_run import dry_run_class, is_dry_run
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import write_stdout


def _resolve_home(repo_dir: Path) -> Path:
    """The home directory that holds Claude Code sessions or history."""
    if (repo_dir / "home").is_dir():
        return repo_dir / "home"
    if (repo_dir / ".claude").is_dir() or (repo_dir / ".zsh_history").is_file():
        return repo_dir
    return Path.home()


def _filter_tracked(findings: Sequence[Finding], repo_dir: Path) -> tuple[Finding, ...]:
    """Mark findings tracked if an open issue of the repository names them."""
    try:
        from devops_cli.core.repo import find_repo_root
        from devops_cli.git.remotes import get_repo_origin_name

        root = find_repo_root(repo_dir)
        target = get_repo_origin_name(root)
        if target and "/" in target:
            open_issues = GitHubTrackedIssues(target).open_issues()
            return mark_tracked(findings, open_issues)
    except Exception:
        pass
    return tuple(findings)


def _file_and_announce(findings: Sequence[Finding], repo_dir: Path) -> None:
    """File drafts through devops roadmap intake and announce results."""
    groups = groups_of(findings)
    drafts = drafts_of(groups)
    filed = file_drafts(drafts, cwd=repo_dir)
    for item in filed:
        if item.number is not None:
            write_stdout(
                MESSAGES.ai.agent_audit_filed.format(number=item.number, title=item.title) + "\n"
            )
        else:
            write_stdout(MESSAGES.ai.agent_audit_candidate_unfiled.format(title=item.title) + "\n")


def _store_counts(findings: Sequence[Finding]) -> None:
    """Merge findings into the daily audit counts store."""
    try:
        today_store = store_path(date.today())
        merge_counts(today_store, findings)
    except Exception:
        pass


@dry_run_class("request-plan")
def run_agent_audit_cmd(
    since: Annotated[
        int,
        typer.Option("--since", help=HELP.ai.agent_audit_since),
    ] = 30,
    source: Annotated[
        str | None,
        typer.Option("--source", help=HELP.ai.agent_audit_source),
    ] = None,
    repo_dir: Annotated[
        Path | None,
        typer.Option("--repo-dir", help=HELP.ai.agent_audit_repo_dir),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help=HELP.options.json_output),
    ] = False,
    plan: Annotated[
        bool,
        typer.Option("--plan", help=HELP.ai.agent_audit_plan),
    ] = False,
    confirm: Annotated[
        bool,
        typer.Option("--confirm", help=HELP.ai.agent_audit_confirm),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Count recurring problems across agent sessions, group findings, and file candidate drafts."""
    if (dry_run or is_dry_run()) and confirm:
        raise typer.BadParameter(MESSAGES.ai.agent_audit_dry_run_with_confirm)

    target_repo = (repo_dir or Path.cwd()).resolve()
    home = _resolve_home(target_repo)
    sources = resolve_sources(source)
    records = read_sources(sources, repo_dir=target_repo, home=home, since_days=since)
    ranked = rank_findings(build_findings(records))
    output_format = "json" if json_output else "table"

    if dry_run or is_dry_run():
        write_stdout(render_report(ranked, output_format=output_format))
        return

    findings = group_findings(_filter_tracked(ranked, target_repo))
    if not plan:
        _store_counts(findings)

    write_stdout(render_report(findings, output_format=output_format))
    if confirm:
        _file_and_announce(findings, target_repo)
