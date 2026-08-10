"""Manage AI provider configuration (Ollama, Claude, Copilot/OpenAI)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Annotated

import typer
from rich import print as rprint
from rich.console import Console
from rich.rule import Rule
from rich.table import Table

from devops_cli.cli import new_typer
from devops_cli.config import SecretStorageError, dotted_set
from devops_cli.env_vars import env_var_for_option

app = new_typer(
    help="Configure and test AI providers (Ollama, Claude, Copilot).",
    no_args_is_help=True,
)
console = Console()

_PROVIDERS = ("ollama", "claude", "copilot", "openai")

# ── Agent file targets ────────────────────────────────────────────────────────

_AGENT_FILES: dict[str, str] = {
    "AGENTS.md": "Generic agent instructions (Codex, custom agents)",
    "CLAUDE.md": "Claude-specific instructions",
    ".github/copilot-instructions.md": "GitHub Copilot workspace instructions",
}

_AGENT_SYSTEM_PROMPT = """\
You are an Enterprise Infrastructure Architect writing precise, structured \
instructions for AI coding agents. Your output will be read by AI assistants \
(GitHub Copilot, Claude, Codex) to understand the project and assist developers.

Guidelines:
- Be concise and factual — no marketing language
- Include exact commands, paths, and conventions
- Highlight security-sensitive areas
- Cover build, test, lint, and deploy workflows
- Note non-obvious architecture decisions
"""


def _collect_project_context(repo: Path) -> str:
    """Gather key project files into a single context string."""
    sections: list[str] = []

    # pyproject.toml
    pyproject = repo / "pyproject.toml"
    if pyproject.exists():
        sections.append(f"## pyproject.toml\n```toml\n{pyproject.read_text()}\n```")

    # README
    for name in ("README.md", "README.rst", "README.txt", "README"):
        readme = repo / name
        if readme.exists():
            sections.append(f"## {name}\n{readme.read_text()[:4000]}")
            break

    # Directory tree (2 levels)
    try:
        tree = subprocess.run(
            [
                "find",
                ".",
                "-maxdepth",
                "3",
                "-not",
                "-path",
                "./.git/*",
                "-not",
                "-path",
                "./.venv/*",
                "-not",
                "-path",
                "./__pycache__/*",
            ],
            capture_output=True,
            text=True,
            cwd=repo,
        )
        sections.append(f"## File tree\n```\n{tree.stdout.strip()}\n```")
    except Exception:
        pass

    # .editorconfig
    ec = repo / ".editorconfig"
    if ec.exists():
        sections.append(f"## .editorconfig\n```ini\n{ec.read_text()}\n```")

    # devcontainer.json
    dc = repo / ".devcontainer" / "devcontainer.json"
    if dc.exists():
        sections.append(f"## .devcontainer/devcontainer.json\n```json\n{dc.read_text()}\n```")

    return "\n\n".join(sections)


def _agent_prompt(context: str, target_file: str) -> str:
    return (
        f"Generate the contents of `{target_file}` for this project.\n\n"
        "The file must help AI coding assistants understand the project and work effectively.\n"
        "Include: project purpose, architecture overview, build/test/lint commands, "
        "code conventions, important file paths, security notes, and any non-obvious patterns.\n\n"
        f"{context}"
    )


def _template_content(target_file: str, context_summary: dict[str, str]) -> str:
    """Fallback template when no LLM is configured."""
    name = context_summary.get("name", "devops-cli")
    description = context_summary.get("description", "")
    python_version = context_summary.get("requires_python", ">=3.14")
    entry_point = context_summary.get("entry_point", "")

    shared = f"""\
## Project
**{name}** — {description}

- Language: Python {python_version}
- Entry point: `{entry_point}`
- Virtual environment: `.venv/` (managed by `uv`)

## Build & Test Commands
```bash
uv sync                        # install / sync dependencies
devops ci                      # run all checks (test + lint + format + typecheck)
devops ci test [-v] [-k expr]  # pytest
devops ci lint [--fix]         # ruff check
devops ci format [--fix]       # ruff format
devops ci typecheck            # mypy (strict)
```

## Code Conventions
- Python 3.14+, strict mypy, ruff (E/F/I/N/W/UP rules), 100-char line limit
- 4-space indent for Python; 2-space for JSON/YAML/TOML/shell
- LF line endings, trim trailing whitespace, final newline
- Type annotations on all public functions; `from __future__ import annotations`
- Import `Callable` from `collections.abc`, not `typing`
- Use `httpx2` (not `httpx`) for HTTP — `import httpx2`
- Secrets stored in OS keyring via `keyring`; never in config files or env vars

## Architecture
```
src/devops_cli/
  main.py              # Typer app, command registration
  config.py            # Pydantic Settings, keyring helpers
  commands/            # One file per command group
  ai/
    client.py          # Unified LLM client (Ollama / Claude / OpenAI-compat)
    personas.py        # Reviewer persona definitions (DevSecOps, Architect, PM, Auditor)
  github/client.py     # PyGithub + httpx2 wrapper
  git/operations.py    # GitPython helpers
  crypto/ssh_keys.py   # SSH key generation / rotation
  templates/           # Jinja2 templates for devcontainer scaffolding
tests/                 # pytest, pytest-asyncio, pytest-mock
```

## AI Features (`devops ai`, `devops review`)
- `devops ai config --provider <ollama|claude|copilot|openai>`
- `devops ai test` — verify LLM connectivity
- `devops ai agents` — (re)generate this file and siblings
- `devops review branch [<branch>] [--base main] [--persona <p>] [--all]`
- `devops review pr <number> [--post]` — review GitHub PRs; optionally post as comment
- Personas: `devsecops` · `architect` · `pm` · `auditor`

## Security Notes
- SSH private keys: `~/.ssh/id_ed25519-<YYYYMMM>` pattern; rotated every 90 days
- GitHub / Grafana / ArgoCD tokens stored in OS keyring only
- All HTTP clients use `httpx2` with explicit timeouts
- No credentials in config YAML or source files
"""

    if "CLAUDE.md" in target_file:
        return f"# {name} — Claude Instructions\n\n{shared}"
    if "copilot" in target_file:
        return f"# GitHub Copilot Instructions\n\n{shared}"
    return f"# {name} — Agent Instructions\n\n{shared}"


def _parse_pyproject(repo: Path) -> dict[str, str]:
    """Extract key fields from pyproject.toml without a TOML parser dependency."""
    result: dict[str, str] = {}
    pp = repo / "pyproject.toml"
    if not pp.exists():
        return result
    for line in pp.read_text().splitlines():
        line = line.strip()
        if line.startswith("name = "):
            result["name"] = line.split("=", 1)[1].strip().strip('"')
        elif line.startswith("description = "):
            result["description"] = line.split("=", 1)[1].strip().strip('"')
        elif line.startswith("requires-python = "):
            result["requires_python"] = line.split("=", 1)[1].strip().strip('"')
        elif "devops_cli.main:app" in line or "main:app" in line:
            result["entry_point"] = line.split("=", 1)[0].strip().strip('"')
    return result


@app.command()
def config(
    provider: Annotated[
        str | None,
        typer.Option("--provider", "-p", help=f"Provider: {', '.join(_PROVIDERS)}"),
    ] = None,
    model: Annotated[
        str | None,
        typer.Option("--model", "-m", help="Model name, e.g. llama3.2, claude-opus-4-5"),
    ] = None,
    ollama_url: Annotated[
        str | None,
        typer.Option("--ollama-url", help="Ollama server base URL"),
    ] = None,
    api_base_url: Annotated[
        str | None,
        typer.Option("--api-base-url", help="Override API base URL for any provider"),
    ] = None,
    api_key: Annotated[
        str | None,
        typer.Option("--api-key", help="API key — stored in OS keyring, not config file"),
    ] = None,
) -> None:
    """Show or update AI provider configuration."""
    from devops_cli.config import get_ai_api_key, load_settings, save_settings

    settings = load_settings()

    if not any([provider, model, ollama_url, api_base_url, api_key]):
        ai = settings.ai
        current_key = get_ai_api_key(settings)
        table = Table(title="AI Configuration")
        table.add_column("Setting", style="cyan")
        table.add_column("Value")
        table.add_row("provider", ai.provider)
        table.add_row("model", ai.model)
        table.add_row("ollama_url", ai.ollama_url)
        table.add_row("api_base_url", ai.api_base_url or "(default)")
        key_display = "[green]***set***[/green]" if current_key else "[dim](not set)[/dim]"
        table.add_row("api_key", key_display)
        console.print(table)
        return

    if provider:
        if provider not in _PROVIDERS:
            rprint(f"[red]Unknown provider {provider!r}. Choose: {', '.join(_PROVIDERS)}[/red]")
            raise typer.Exit(1)
        settings.ai.provider = provider
    if model:
        settings.ai.model = model
    if ollama_url:
        settings.ai.ollama_url = ollama_url
    if api_base_url:
        settings.ai.api_base_url = api_base_url
    if api_key:
        try:
            dotted_set(settings, "ai.api_key", api_key)
            rprint("[green]✓[/green] API key saved to keyring")
        except SecretStorageError as exc:
            rprint(f"[red]Could not store ai.api_key: {exc}[/red]")
            env_var = env_var_for_option("ai.api_key")
            if env_var:
                rprint(
                    f"[yellow]Use environment variable fallback: export {env_var}=<value>[/yellow]"
                )
            raise typer.Exit(1)

    save_settings(settings)
    rprint("[green]✓[/green] AI configuration saved")


@app.command()
def models() -> None:
    """List available models for the configured provider."""
    from devops_cli.ai.client import LLMClient
    from devops_cli.config import get_ai_api_key, load_settings

    settings = load_settings()
    client = LLMClient(settings.ai, api_key=get_ai_api_key(settings))
    try:
        model_list = client.list_models()
    except Exception as exc:
        rprint(f"[red]Failed to list models: {exc}[/red]")
        raise typer.Exit(1)

    table = Table(title=f"Available Models — {settings.ai.provider}")
    table.add_column("Model", style="cyan")
    for m in model_list:
        table.add_row(m)
    console.print(table)


@app.command()
def test(
    prompt: Annotated[
        str,
        typer.Option("--prompt", "-p", help="Test prompt to send to the provider"),
    ] = "Reply with exactly one word: OK",
) -> None:
    """Send a test prompt to verify AI provider connectivity."""
    from devops_cli.ai.client import LLMClient
    from devops_cli.config import get_ai_api_key, load_settings

    settings = load_settings()
    rprint(
        f"Provider: [cyan]{settings.ai.provider}[/cyan]  Model: [cyan]{settings.ai.model}[/cyan]"
    )
    client = LLMClient(settings.ai, api_key=get_ai_api_key(settings))
    try:
        reply = client.chat(system="You are a helpful assistant.", user=prompt)
        rprint(f"[green]✓[/green] {reply.strip()}")
    except Exception as exc:
        rprint(f"[red]✗ Failed: {exc}[/red]")
        raise typer.Exit(1)


@app.command()
def agents(
    repo: Annotated[
        Path,
        typer.Option("--repo", "-r", help="Repository root (default: current directory)"),
    ] = Path("."),
    template: Annotated[
        bool,
        typer.Option("--template", help="Generate from built-in template without calling the LLM"),
    ] = False,
    files: Annotated[
        list[str],
        typer.Option("--file", "-f", help="Files to generate (repeatable)"),
    ] = list(_AGENT_FILES),
) -> None:
    """Generate LLM/Agent instruction files (AGENTS.md, CLAUDE.md, copilot-instructions.md)."""
    from devops_cli.ai.client import LLMClient
    from devops_cli.config import get_ai_api_key, load_settings

    repo = repo.resolve()
    meta = _parse_pyproject(repo)

    use_llm = not template
    client: LLMClient | None = None

    if use_llm:
        settings = load_settings()
        try:
            client = LLMClient(settings.ai, api_key=get_ai_api_key(settings))
            context = _collect_project_context(repo)
        except Exception as exc:
            rprint(f"[yellow]LLM unavailable ({exc}), falling back to template.[/yellow]")
            use_llm = False

    for target in files:
        dest = repo / target
        console.print(Rule(f" {target} ", style="cyan"))

        if use_llm and client is not None:
            rprint(f"Generating [cyan]{target}[/cyan] via LLM...")
            try:
                content = client.chat(
                    system=_AGENT_SYSTEM_PROMPT,
                    user=_agent_prompt(context, target),
                )
            except Exception as exc:
                rprint(f"[yellow]LLM failed ({exc}), using template.[/yellow]")
                content = _template_content(target, meta)
        else:
            content = _template_content(target, meta)

        dest.parent.mkdir(parents=True, exist_ok=True)
        if not content.endswith("\n"):
            content += "\n"
        dest.write_text(content, encoding="utf-8")
        rprint(f"[green]✓[/green] Written: {dest.relative_to(repo)}")
