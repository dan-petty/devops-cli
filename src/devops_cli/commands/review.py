"""AI-powered code review for git branches and GitHub pull requests."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Annotated, Any

import typer
from rich import print as rprint
from rich.console import Console
from rich.rule import Rule

from devops_cli.ai.personas import PERSONAS, Persona, PersonaDefinition

app = typer.Typer(
    help="AI-powered code reviews using expert personas.",
    no_args_is_help=True,
)
console = Console()

_MAX_DIFF_CHARS = 80_000  # stay within typical LLM context windows


# ── helpers ───────────────────────────────────────────────────────────────────


def _personas_to_run(all_personas: bool, persona: Persona | None) -> list[PersonaDefinition]:
    if all_personas:
        return list(PERSONAS.values())
    return [PERSONAS[persona or Persona.DEVSECOPS]]


def _build_prompt(diff: str, title: str) -> str:
    truncated = len(diff) > _MAX_DIFF_CHARS
    snippet = diff[:_MAX_DIFF_CHARS]
    suffix = "\n[diff truncated to fit context window]" if truncated else ""
    return (
        f"Please review the following code changes.\n\n"
        f"## {title}\n\n"
        f"```diff\n{snippet}\n```{suffix}\n"
    )


def _run_review(diff: str, title: str, persona: PersonaDefinition, client: Any) -> str:
    return str(client.chat(system=persona.system_prompt, user=_build_prompt(diff, title)))


def _print_review(persona: PersonaDefinition, review: str) -> None:
    from rich.markdown import Markdown

    console.print()
    console.print(Rule(f" {persona.title} ", style="bold magenta"))
    console.print(Markdown(review))


def _collect_files(root: Path, pattern: str) -> str:
    """Read matching source files under root and return as annotated text."""
    chunks: list[str] = []
    total = 0
    for p in sorted(root.rglob(pattern)):
        if any(part in {".venv", "__pycache__", ".git", ".mypy_cache"} for part in p.parts):
            continue
        rel = p.relative_to(root)
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        block = f"### {rel}\n```python\n{text}\n```"
        if total + len(block) > _MAX_DIFF_CHARS:
            chunks.append("*(remaining files truncated to fit context window)*")
            break
        chunks.append(block)
        total += len(block)
    return "\n\n".join(chunks)


def _build_path_prompt(content: str, title: str) -> str:
    return (
        f"Please review the following source files for security, quality, and "
        f"architecture concerns.\n\n## {title}\n\n{content}"
    )


# ── path ──────────────────────────────────────────────────────────────────────


@app.command()
def path(
    target: Annotated[
        Path,
        typer.Argument(help="File or directory to review"),
    ] = Path("."),
    pattern: Annotated[
        str,
        typer.Option("--pattern", "-g", help="Glob pattern for files (used when target is a dir)"),
    ] = "*.py",
    persona: Annotated[
        Persona | None,
        typer.Option("--persona", "-p", help="Reviewer persona"),
    ] = None,
    all_personas: Annotated[
        bool,
        typer.Option("--all", help="Run all four reviewer personas"),
    ] = False,
) -> None:
    """Review source files directly (no git required)."""
    from devops_cli.ai.client import AIClientError, LLMClient
    from devops_cli.config import get_ai_api_key, load_settings

    target = target.resolve()
    if target.is_file():
        content = f"### {target.name}\n```python\n{target.read_text(encoding='utf-8')}\n```"
        title = str(target.name)
    else:
        rprint(f"Collecting [cyan]{pattern}[/cyan] files under [dim]{target}[/dim]...")
        content = _collect_files(target, pattern)
        title = str(target)

    if not content.strip():
        rprint("[yellow]No files found.[/yellow]")
        raise typer.Exit(0)

    settings = load_settings()
    client = LLMClient(settings.ai, api_key=get_ai_api_key(settings))

    try:
        for pd in _personas_to_run(all_personas, persona):
            rprint(f"Reviewing as [bold magenta]{pd.title}[/bold magenta]...")
            _print_review(
                pd, client.chat(system=pd.system_prompt, user=_build_path_prompt(content, title))
            )
    except AIClientError as exc:
        rprint(f"[red]AI provider error:[/red] {exc}")
        raise typer.Exit(1)


# ── branch ────────────────────────────────────────────────────────────────────


@app.command()
def branch(
    branch_name: Annotated[
        str | None,
        typer.Argument(help="Branch to review (default: current branch)"),
    ] = None,
    base: Annotated[
        str,
        typer.Option("--base", "-b", help="Base branch to diff against"),
    ] = "main",
    persona: Annotated[
        Persona | None,
        typer.Option("--persona", "-p", help="Reviewer persona"),
    ] = None,
    all_personas: Annotated[
        bool,
        typer.Option("--all", help="Run all four reviewer personas"),
    ] = False,
    repo_path: Annotated[
        Path,
        typer.Option("--repo", help="Path to the git repository"),
    ] = Path("."),
) -> None:
    """Review a git branch diff with one or all AI personas."""
    from devops_cli.ai.client import AIClientError, LLMClient
    from devops_cli.config import get_ai_api_key, load_settings

    if branch_name is None:
        proc = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            cwd=repo_path,
        )
        branch_name = proc.stdout.strip()

    rprint(f"Diffing [cyan]{branch_name}[/cyan] against [cyan]{base}[/cyan]...")

    diff_proc = subprocess.run(
        ["git", "diff", f"{base}...{branch_name}"],
        capture_output=True,
        text=True,
        cwd=repo_path,
    )
    if diff_proc.returncode != 0:
        rprint(f"[red]git diff failed: {diff_proc.stderr.strip()}[/red]")
        raise typer.Exit(1)
    if not diff_proc.stdout.strip():
        rprint("[yellow]No differences found between branches.[/yellow]")
        return

    settings = load_settings()
    client = LLMClient(settings.ai, api_key=get_ai_api_key(settings))
    title = f"Branch `{branch_name}` vs `{base}`"

    try:
        for pd in _personas_to_run(all_personas, persona):
            rprint(f"Reviewing as [bold magenta]{pd.title}[/bold magenta]...")
            _print_review(pd, _run_review(diff_proc.stdout, title, pd, client))
    except AIClientError as exc:
        rprint(f"[red]AI provider error:[/red] {exc}")
        raise typer.Exit(1)


# ── pr ────────────────────────────────────────────────────────────────────────


@app.command()
def pr(
    number: Annotated[int, typer.Argument(help="Pull request number")],
    repo: Annotated[
        str | None,
        typer.Option("--repo", "-r", help="owner/repo (default: detected from git remote)"),
    ] = None,
    persona: Annotated[
        Persona | None,
        typer.Option("--persona", "-p", help="Reviewer persona"),
    ] = None,
    all_personas: Annotated[
        bool,
        typer.Option("--all", help="Run all four reviewer personas"),
    ] = False,
    post_comment: Annotated[
        bool,
        typer.Option("--post", help="Post the review as a comment on the GitHub PR"),
    ] = False,
) -> None:
    """Review a GitHub pull request with one or all AI personas."""
    from devops_cli.ai.client import AIClientError, LLMClient
    from devops_cli.config import get_ai_api_key, get_github_token, load_settings
    from devops_cli.github.client import GitHubClient

    settings = load_settings()
    token = get_github_token(settings)
    if not token:
        rprint(
            "[red]GitHub token not configured. Run: devops config set github.token <token>[/red]"
        )
        raise typer.Exit(1)

    if repo is None:
        proc = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
        )
        raw = proc.stdout.strip()
        repo = (
            raw.removeprefix("https://github.com/")
            .removeprefix("git@github.com:")
            .removesuffix(".git")
        )

    rprint(f"Fetching PR [cyan]#{number}[/cyan] from [cyan]{repo}[/cyan]...")
    gh = GitHubClient(token)
    pull = gh.get_pull(repo, number)
    diff = gh.get_pr_diff(repo, number)
    title = f"PR #{number}: {pull.title}"

    client = LLMClient(settings.ai, api_key=get_ai_api_key(settings))
    reviews: list[tuple[PersonaDefinition, str]] = []

    try:
        for pd in _personas_to_run(all_personas, persona):
            rprint(f"Reviewing as [bold magenta]{pd.title}[/bold magenta]...")
            review_text = _run_review(diff, title, pd, client)
            _print_review(pd, review_text)
            reviews.append((pd, review_text))
    except AIClientError as exc:
        rprint(f"[red]AI provider error:[/red] {exc}")
        raise typer.Exit(1)

    if post_comment and reviews:
        sections = "\n\n---\n\n".join(f"## Review by {pd.title}\n\n{text}" for pd, text in reviews)
        pull.create_issue_comment(f"## 🤖 AI Code Review\n\n{sections}")
        rprint(f"\n[green]✓[/green] Review posted as comment on PR #{number}")
