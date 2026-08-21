"""Manage AI provider configuration (Ollama, Claude, Copilot/OpenAI)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Annotated, Any

import typer
from rich import print as rprint
from rich.console import Console
from rich.rule import Rule
from rich.table import Table

from devops_cli.ai.personas import PERSONAS, Persona
from devops_cli.commands.analyze import app as analyze_app
from devops_cli.commands.rag import app as rag_app
from devops_cli.commands.review import app as review_app
from devops_cli.config.constants import (
    CONST_AGENTS_MD_FILENAME,
    CONST_DEVCONTAINER_JSON_PATH,
    CONST_GIT_DIR_NAME,
)
from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
from devops_cli.config.env import env_var_for_option
from devops_cli.config.options import AI_API_KEY
from devops_cli.config.settings import SecretStorageError, dotted_set
from devops_cli.core.cli import new_typer

app = new_typer(
    help="Configure, test, chat, analyze, and review codebases (Ollama, Claude, Copilot).",
    no_args_is_help=True,
)
app.add_typer(
    review_app,
    name="review",
    help="AI-powered code reviews using expert personas (devsecops, architect, pm, auditor, qa).",
)
app.add_typer(
    analyze_app,
    name="analyze",
    help="Analyze codebase metadata and create/update .data/analysis/*-metadata.json files.",
)
app.add_typer(
    rag_app,
    name="rag",
    help="Manage RAG vector embeddings, indexing, and semantic code search (Qdrant).",
)
console = Console()

_PROVIDERS = ("ollama", "claude", "copilot", "openai")

# ── Agent file targets ────────────────────────────────────────────────────────

_AGENT_FILES: dict[str, str] = {
    CONST_AGENTS_MD_FILENAME: "Canonical agent instructions (single source of truth)",
    "CLAUDE.md": "Pointer stub redirecting Claude Code to AGENTS.md",
    ".github/copilot-instructions.md": "Pointer stub redirecting GitHub Copilot to AGENTS.md",
}

_TASKS_DIR = Path(__file__).resolve().parent.parent / "ai" / "tasks"


def _load_task_prompt(filename: str) -> str:
    path = _TASKS_DIR / filename
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""


# Task-specific addendum appended to the architect persona when generating AGENTS.md
_AGENTS_TASK_ADDENDUM = "\n" + _load_task_prompt("generate_agents.md")


def _try_retrieve_rag_context(query: str, top_k: int = 3) -> str | None:
    """Attempt to retrieve relevant semantic context from RAG vector store."""
    try:
        from devops_cli.ai.rag.embeddings import EmbeddingsEngine
        from devops_cli.ai.rag.qdrant import QdrantClient
        from devops_cli.ai.rag.retriever import SemanticRetriever
        from devops_cli.config.settings import get_ai_api_key, load_settings

        settings = load_settings()
        if not settings.ai.rag.enabled:
            return None

        qdrant = QdrantClient(
            base_url=settings.qdrant.url or "http://localhost:6333",
            allow_private_network=settings.ai.allow_private_network,
        )
        if not qdrant.is_alive():
            return None

        embedder = EmbeddingsEngine(ai_config=settings.ai, api_key=get_ai_api_key(settings))
        retriever = SemanticRetriever(
            qdrant=qdrant,
            embedder=embedder,
            code_collection=f"{settings.qdrant.collection_prefix}_code",
            docs_collection=f"{settings.qdrant.collection_prefix}_docs",
            default_top_k=top_k,
        )
        ctx = retriever.retrieve_context(query, top_k=top_k)
        if ctx.has_results:
            return ctx.formatted_text
    except Exception:
        pass
    return None


def _collect_project_context(repo: Path) -> str:
    """Gather key project files into a single context string."""
    sections: list[str] = []

    # pyproject.toml
    pyproject = repo / "pyproject.toml"
    if pyproject.exists():
        sections.append(f"## pyproject.toml\n```toml\n{pyproject.read_text()}\n```")

    from devops_cli.ai.review.sanitization import _sanitize_prompt_boundary_tags

    # README
    for name in ("README.md", "README.rst", "README.txt", "README"):
        readme = repo / name
        if readme.exists():
            clean_readme = _sanitize_prompt_boundary_tags(readme.read_text()[:4000])
            sections.append(
                f"## {name}\n"
                f'<project_context_file name="{name}">\n'
                f"{clean_readme}\n"
                f"</project_context_file>"
            )
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
                f"./{CONST_GIT_DIR_NAME}/*",
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
            timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
        )
        clean_tree = _sanitize_prompt_boundary_tags(tree.stdout.strip())
        sections.append(f"## File tree\n```\n{clean_tree}\n```")
    except (OSError, subprocess.SubprocessError):
        pass

    # .editorconfig
    ec = repo / ".editorconfig"
    if ec.exists():
        clean_ec = _sanitize_prompt_boundary_tags(ec.read_text()[:4000])
        sections.append(
            "## .editorconfig\n"
            '<project_context_file name=".editorconfig">\n'
            f"{clean_ec}\n"
            "</project_context_file>"
        )

    # devcontainer.json
    dc = repo / CONST_DEVCONTAINER_JSON_PATH
    if dc.exists():
        sections.append(f"## {CONST_DEVCONTAINER_JSON_PATH}\n```json\n{dc.read_text()}\n```")

    # Semantic RAG Architecture Context
    rag_ctx = _try_retrieve_rag_context(
        f"{repo.name} architecture CLI commands conventions", top_k=4
    )
    if rag_ctx:
        sections.append(f"## Indexed Architecture & Subsystem Context\n{rag_ctx}")

    return "\n\n".join(sections)


def _agent_prompt(context: str, target_file: str) -> str:
    return (
        f"Generate the contents of `{target_file}` for this project.\n\n"
        "The file must help AI coding assistants understand the project and work effectively.\n"
        "Include: project purpose, architecture overview, build/test/lint commands, "
        "code conventions, important file paths, security notes, and any non-obvious patterns.\n\n"
        f"{context}"
    )


_CANONICAL_AGENT_FILE = CONST_AGENTS_MD_FILENAME


def _pointer_stub(title: str, tool_name: str, filename: str, canonical_relpath: str) -> str:
    """Thin stub for a tool-specific file that defers to the canonical AGENTS.md."""
    return f"""\
# {title}

> **This file is a pointer, not the source.** {tool_name} looks specifically for
> `{filename}`, so this stub exists to redirect it. All actual instructions — project
> overview, build/test commands, code conventions, architecture, AI features,
> environment & modernization policy, and security notes — live in
> [AGENTS.md]({canonical_relpath}). Read that file. Regenerate both via
> `devops ai agents`; do not duplicate content here.
"""


def _template_content(target_file: str, context_summary: dict[str, str]) -> str:
    """Fallback template when no LLM is configured."""
    name = context_summary.get("name", "Project")
    if target_file == "CLAUDE.md":
        return _pointer_stub(
            f"{name} — Claude Instructions", "Claude Code", "CLAUDE.md", "./AGENTS.md"
        )
    if "copilot" in target_file:
        return _pointer_stub(
            f"{name} — GitHub Copilot Instructions",
            "GitHub Copilot",
            ".github/copilot-instructions.md",
            "../AGENTS.md",
        )
    description = context_summary.get("description", "")
    python_version = context_summary.get("requires_python", ">=3.14")
    entry_point = context_summary.get("entry_point", "")

    return f"""\
# {name} — Agent Instructions & Engineering Best Practices

> **Canonical source.** This file is the single source of truth for AI coding agent
> instructions in this repo. [CLAUDE.md](./CLAUDE.md) and
> [.github/copilot-instructions.md](./.github/copilot-instructions.md) are thin pointers
> to this file.

## 1. Project Overview
**{name}** — {description}

- Language: Python {python_version}
- Entry point: `{entry_point}`
- Virtual environment: `.venv/` (managed by `uv`)

## 2. Core Engineering Philosophy & Best Practices
- **Progressive Testing**: Run targeted, isolated unit tests during active loops;
  defer full CI test suites to the final pre-handoff milestone.
- **Architectural Flexibility**: Prioritize clean abstractions, SOLID principles, and
  separation of concerns. Prefer idiomatic, standard library and established tools.
- **Modern Python Standards**: Strict typing (`mypy --strict`), modern syntax
  (`from __future__ import annotations`, type unions `A | B`), and Pydantic models.
- **Zero-Trust Security**: Never commit plaintext secrets or tokens. Use OS Keyring
  (`keyring`). Enforce SSRF mitigations on network I/O and bounded subprocess timeouts.
- **Target-Agnostic Reviews**: When reviewing target workspaces, evaluate code against
  standard software engineering and security principles (OWASP, CIS, SOLID).

## 3. Build & Test Commands
```bash
uv sync                        # synchronize dependencies
devops ci                      # run full CI quality gate
devops ci test [-v] [-k expr]  # pytest unit test suite
devops ci lint [--fix]         # ruff check
devops ci format [--fix]       # ruff format
devops ci typecheck            # mypy strict static typechecking
devops docs generate --sync-readme  # synchronize CLI documentation and README matrix
```

## 4. Git & Workflow Hygiene
- **Branch Hierarchy**: Topic branches (`feat/*`, `fix/*`, `refactor/*`, `docs/*`)
  target the active release branch (`release/v*`).
- **Conventional Commits**: Format commit messages cleanly (`feat(scope): ...`, `fix(scope): ...`).
- **Zero Direct Commits to `main`**: Maintain PR governance and monitor remote CI checks.
"""


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
        typer.Option("--model", "-m", help="Model name, e.g. gemma4:26b, claude-opus-4-5"),
    ] = None,
    ollama_urls: Annotated[
        str | None,
        typer.Option("--ollama-urls", help="Ollama server base URLs (comma-separated)"),
    ] = None,
    api_base_url: Annotated[
        str | None,
        typer.Option("--api-base-url", help="Override API base URL for any provider"),
    ] = None,
    api_key: Annotated[
        str | None,
        typer.Option("--api-key", help="API key — stored in OS keyring, not config file"),
    ] = None,
    max_retries: Annotated[
        int | None,
        typer.Option("--max-retries", help="Maximum retry count for AI requests upon failure"),
    ] = None,
) -> None:
    """Show or update AI provider configuration."""
    from devops_cli.config.settings import (
        get_ai_api_key,
        load_settings,
        save_settings,
    )

    settings = load_settings()

    if not any([provider, model, ollama_urls, api_base_url, api_key, max_retries is not None]):
        ai = settings.ai
        current_key = get_ai_api_key(settings)
        table = Table(title="AI Configuration")
        table.add_column("Setting", style="cyan")
        table.add_column("Value")
        table.add_row("provider", ai.provider)
        table.add_row("model", ai.model)
        table.add_row("ollama_urls", ", ".join(ai.get_ollama_urls))
        table.add_row("api_base_url", ai.api_base_url or "(default)")
        key_display = "[green]***set***[/green]" if current_key else "[dim](not set)[/dim]"
        table.add_row("api_key", key_display)
        table.add_row("max_retries", str(ai.max_retries))
        console.print(table)
        return

    if provider:
        if provider not in _PROVIDERS:
            rprint(f"[red]Unknown provider {provider!r}. Choose: {', '.join(_PROVIDERS)}[/red]")
            raise typer.Exit(1)
        settings.ai.provider = provider
    if model:
        settings.ai.model = model
    if ollama_urls:
        settings.ai.ollama_urls = [u.strip() for u in ollama_urls.split(",") if u.strip()]
    if api_base_url:
        settings.ai.api_base_url = api_base_url
    if max_retries is not None:
        settings.ai.max_retries = max_retries
    if api_key:
        try:
            dotted_set(settings, AI_API_KEY, api_key)
            rprint("[green]✓[/green] API key saved to keyring")
        except SecretStorageError as exc:
            rprint(f"[red]Could not store ai.api_key: {exc}[/red]")
            env_var = env_var_for_option(AI_API_KEY)
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
    from devops_cli.config.settings import get_ai_api_key, load_settings

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
def preload() -> None:
    """Preload configured model into VRAM across all configured Ollama servers."""
    from devops_cli.ai.client import LLMClient
    from devops_cli.config.settings import get_ai_api_key, load_settings

    settings = load_settings()
    if settings.ai.provider != "ollama":
        p = settings.ai.provider
        rprint(f"[yellow]Model preloading is for Ollama provider (current: {p}).[/yellow]")
        return
    client = LLMClient(settings.ai, api_key=get_ai_api_key(settings))
    rprint(f"Preloading model [bold cyan]{settings.ai.model}[/bold cyan] across Ollama nodes...")
    results = client.preload_models()
    for url, ok in results.items():
        status = "[green]✓ preloaded[/green]" if ok else "[red]✗ failed[/red]"
        rprint(f"  {url}: {status}")


@app.command()
def test(
    prompt: Annotated[
        str,
        typer.Option("--prompt", "-p", help="Test prompt to send to the provider"),
    ] = "Reply with exactly one word: OK",
) -> None:
    """Send a test prompt to verify AI provider connectivity."""
    from devops_cli.ai.client import LLMClient
    from devops_cli.config.settings import get_ai_api_key, load_settings
    from devops_cli.lang import MESSAGES

    settings = load_settings()
    client = LLMClient(settings.ai, api_key=get_ai_api_key(settings))
    rprint(
        f"Testing provider: [cyan]{client.backend_info}[/cyan] | "
        f"model: [cyan]{settings.ai.model}[/cyan]..."
    )
    try:
        test_sys_prompt = _load_task_prompt("test_assistant.md")
        reply = client.chat(system=test_sys_prompt, user=prompt)
        rprint(MESSAGES.ai.test_success.format(reply=reply.strip()))
    except Exception as exc:
        rprint(MESSAGES.ai.test_failed.format(exc=exc))
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
    from devops_cli.config.settings import get_ai_api_key, load_settings

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
        from devops_cli.lang import MESSAGES

        dest = (repo / target).resolve()
        repo_resolved = repo.resolve()
        if not (dest == repo_resolved or dest.is_relative_to(repo_resolved)):
            msg = MESSAGES.messages.target_path_outside_repo.format(dest=dest)
            rprint(f"[red]{msg}[/red]")
            continue
        console.print(Rule(f" {target} ", style="cyan"))

        # Only the canonical file is worth spending an LLM call on — the others
        # are static pointers to it, so they always use the template.
        if target != _CANONICAL_AGENT_FILE:
            content = _template_content(target, meta)
        elif use_llm and client is not None:
            rprint(MESSAGES.ai.generating_agents.format(target=f"[cyan]{target}[/cyan]"))
            system = PERSONAS[Persona.ARCHITECT].system_prompt + _AGENTS_TASK_ADDENDUM
            try:
                content = client.chat(
                    system=system,
                    user=_agent_prompt(context, target),
                )
            except Exception as exc:
                msg = MESSAGES.messages.llm_failed_template_fallback.format(exc=exc)
                rprint(f"[yellow]{msg}[/yellow]")
                content = _template_content(target, meta)
        else:
            content = _template_content(target, meta)

        dest.parent.mkdir(parents=True, exist_ok=True)
        if not content.endswith("\n"):
            content += "\n"
        dest.write_text(content, encoding="utf-8")
        rprint(MESSAGES.ai.written_file.format(path=dest.relative_to(repo)))


_PERSONA_NAMES = [p.value for p in Persona]


@app.command()
def chat(
    persona: Annotated[
        str,
        typer.Option(
            "--persona",
            "-p",
            help=f"Persona to chat with: {', '.join(_PERSONA_NAMES)}",
        ),
    ] = Persona.ARCHITECT,
    context_file: Annotated[
        Path | None,
        typer.Option(
            "--context",
            "-c",
            help="Optional file to inject as background context (e.g. AGENTS.md)",
            exists=True,
            readable=True,
        ),
    ] = None,
    rag: Annotated[
        bool, typer.Option("--rag/--no-rag", help="Retrieve relevant semantic RAG context")
    ] = True,
    stream: Annotated[
        bool, typer.Option("--stream/--no-stream", help="Stream response tokens")
    ] = True,
    tools: Annotated[
        bool, typer.Option("--tools/--no-tools", help="Enable DevOps agent tools")
    ] = True,
    thinking: Annotated[
        bool, typer.Option("--thinking/--no-thinking", help="Enable model reasoning/thinking")
    ] = True,
    prewarm: Annotated[
        bool, typer.Option("--prewarm/--no-prewarm", help="Prewarm the model before starting chat")
    ] = True,
) -> None:
    """Start an interactive chat with a Pydantic AI persona (tools, thinking, streaming, RAG)."""
    import sys

    from devops_cli.ai.agents import PydanticAgent
    from devops_cli.ai.client import LLMClient
    from devops_cli.ai.tools import get_persona_tools
    from devops_cli.config.settings import get_ai_api_key, load_settings

    if persona not in _PERSONA_NAMES:
        rprint(f"[red]Unknown persona {persona!r}. Choose: {', '.join(_PERSONA_NAMES)}[/red]")
        raise typer.Exit(1)

    persona_def = PERSONAS[Persona(persona)]
    system = persona_def.chat_prompt
    if context_file is not None:
        system = system + "\n\n## Project Context\n\n" + context_file.read_text(encoding="utf-8")

    settings = load_settings()
    client = LLMClient(settings.ai.for_task("chat"), api_key=get_ai_api_key(settings))

    if prewarm and client._config.provider == "ollama":
        ollama_urls = client._config.get_ollama_urls
        if ollama_urls:
            n_nodes = len(ollama_urls)
            rprint(f"[dim]Prewarming model '{settings.ai.model}' across {n_nodes} node(s)...[/dim]")
            preload_results = client.preload_models()
            for url, ok in preload_results.items():
                status = (
                    "[dim green]✓ ready[/dim green]"
                    if ok
                    else "[dim yellow]✗ offline/skipped[/dim yellow]"
                )
                rprint(f"[dim]  {url}: {status}[/dim]")

    agent_tools = get_persona_tools(persona) if tools else []
    agent: PydanticAgent[Any] = PydanticAgent(
        client=client, system_prompt=system, tools=agent_tools
    )

    console.print(
        Rule(
            f" [cyan]{persona_def.title}[/cyan] (Pydantic Agent)  "
            f"[dim]{client.backend_info} / {settings.ai.model}[/dim] ",
            style="cyan",
        )
    )
    rprint("[dim]Type your message and press Enter. Ctrl+C or [bold]exit[/bold] to quit.[/dim]\n")

    while True:
        try:
            user_input = console.input("[bold cyan]You:[/bold cyan] ").strip()
        except (EOFError, KeyboardInterrupt):
            from devops_cli.lang import MESSAGES

            rprint(f"\n[dim]{MESSAGES.messages.goodbye}[/dim]")
            break

        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit", "/exit", "/quit"}:
            rprint("[dim]Goodbye.[/dim]")
            break

        effective_prompt = user_input
        if rag:
            rag_snippet = _try_retrieve_rag_context(user_input, top_k=3)
            if rag_snippet:
                effective_prompt = f"{rag_snippet}\n\nUser Question: {user_input}"

        try:
            rprint(f"\n[green]{persona_def.title}:[/green] ", end="")
            sys.stdout.flush()

            from devops_cli.ai.thinking import strip_think_blocks

            if stream and not tools:
                from devops_cli.ai.thinking import ThinkingStreamProcessor

                processor = ThinkingStreamProcessor(
                    show_thinking=thinking,
                    console=console,
                )
                system_with_tools = agent._build_system_prompt_with_tools()
                messages = agent.memory.to_chat_messages()
                for chunk in client.chat_messages_stream(
                    system_with_tools, messages, enable_thinking=thinking
                ):
                    processor.feed(chunk)
                processor.flush()
                reply = processor.clean_content
                if not reply.strip() and processor.thinking_content:
                    # Model put all output in thinking tags; retrieve summary
                    agent_res = agent.run(effective_prompt, enable_thinking=thinking)
                    reply = strip_think_blocks(agent_res.content)
                    if reply.strip():
                        rprint(f"{reply.strip()}\n")
                else:
                    rprint("\n")
                    agent.memory.add_interaction("assistant", reply)
            else:

                def _print_thought(th: str) -> None:
                    if thinking:
                        from rich.markup import escape

                        rprint(
                            f"\n[dim cyan]💭 Thinking...[/dim cyan]\n"
                            f"[dim italic]{escape(th)}[/dim italic]\n"
                            f"[dim cyan]✓ Thought complete[/dim cyan]\n"
                        )

                def _print_tool(t_name: str, t_args: dict[str, Any], t_res: Any) -> None:
                    args_str = ", ".join(f"{k}={v!r}" for k, v in t_args.items())
                    if len(args_str) > 60:
                        args_str = args_str[:57] + "..."
                    tool_msg = (
                        f"\n[dim yellow]🔧 Tool: [bold]{t_name}[/bold]({args_str})[/dim yellow]"
                    )
                    rprint(tool_msg)
                    res_str = str(t_res).strip()
                    if len(res_str) > 200:
                        res_str = res_str[:197] + "..."
                    rprint(f"[dim green]✓ Result: {res_str}[/dim green]\n")

                agent_res = agent.run(
                    effective_prompt,
                    enable_thinking=thinking,
                    on_thought=_print_thought if thinking else None,
                    on_tool_call=_print_tool,
                )

                reply = strip_think_blocks(agent_res.content)
                rprint(f"{reply.strip()}\n")

        except Exception as exc:
            rprint(f"\n[red]Error: {exc}[/red]\n")
            if agent.memory.entries:
                agent.memory.entries.pop()  # don't add failed turn to history
            continue

        if agent.memory.auto_summarize_if_needed(llm_client=client):
            rprint("[dim]⚡ Long conversation memory consolidated into context summary.[/dim]")


@app.command("bundle-models")
def bundle_models(
    output_dir: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output directory for model archive bundle"),
    ] = None,
) -> None:
    """Bundle Ollama model metadata into tarball for air-gapped DevContainers."""
    from devops_cli.ai.bundle import bundle_ollama_models

    count, manifest_path = bundle_ollama_models(output_dir=output_dir)
    rprint(f"[green]✓ Bundled {count} model(s) → [bold]{manifest_path}[/bold][/green]")


@app.command("pipeline")
def pipeline(
    prompt: Annotated[
        str,
        typer.Argument(
            help="Initial goal or prompt for the multi-agent pipeline",
        ),
    ] = "Perform a multi-agent review of workspace security, architecture, and code quality.",
    personas: Annotated[
        str,
        typer.Option(
            "--personas",
            "-p",
            help="Comma-separated persona pipeline sequence (e.g. devsecops,architect,qa)",
        ),
    ] = "devsecops,architect,qa",
    max_turns: Annotated[
        int,
        typer.Option("--max-turns", help="Maximum tool turns per agent stage"),
    ] = 5,
    rag: Annotated[
        bool, typer.Option("--rag/--no-rag", help="Retrieve relevant semantic RAG context")
    ] = True,
    thinking: Annotated[
        bool,
        typer.Option("--thinking/--no-thinking", help="Enable reasoning/thinking per agent"),
    ] = True,
) -> None:
    """Run a multi-agent Pydantic pipeline with shared DevOps tools and RAG context."""
    from devops_cli.ai.agents import PydanticAgent
    from devops_cli.ai.agents.pipeline import MultiAgentPipeline
    from devops_cli.ai.client import LLMClient
    from devops_cli.ai.tools import get_default_tools, get_persona_tools
    from devops_cli.config.settings import get_ai_api_key, load_settings
    from devops_cli.dry_run import CommandDryRunResult, is_dry_run

    persona_names = [p.strip().lower() for p in personas.split(",") if p.strip()]
    valid_personas: list[Persona] = []
    for name in persona_names:
        if name not in _PERSONA_NAMES:
            rprint(f"[red]Unknown persona {name!r}. Choose from: {', '.join(_PERSONA_NAMES)}[/red]")
            raise typer.Exit(1)
        valid_personas.append(Persona(name))

    if is_dry_run():
        res = CommandDryRunResult(
            command="devops ai pipeline",
            target=prompt,
            action="multi_agent_pipeline_execution",
            details={
                "personas": [p.value for p in valid_personas],
                "prompt": prompt,
                "max_turns": max_turns,
                "rag": rag,
            },
        )
        rprint("[yellow][dry-run][/yellow] Command response:")
        console.print_json(res.model_dump_json(indent=2))
        return

    settings = load_settings()
    client = LLMClient(settings.ai.for_task("chat"), api_key=get_ai_api_key(settings))
    agent_tools = get_default_tools()

    pipeline_engine: MultiAgentPipeline[Any] = MultiAgentPipeline(
        shared_tools=agent_tools,
    )

    for p in valid_personas:
        p_def = PERSONAS[p]
        stage_tools = get_persona_tools(p)
        agent: PydanticAgent[Any] = PydanticAgent(
            client=client,
            system_prompt=p_def.system_prompt,
            name=p_def.title,
            tools=stage_tools,
        )
        pipeline_engine.add_agent(agent)

    rprint(
        Rule(
            f" [cyan]Multi-Agent Pipeline ({len(valid_personas)} Stages)[/cyan]  "
            f"[dim]{client.backend_info}[/dim] ",
            style="cyan",
        )
    )
    rprint(f"[bold]Initial Prompt:[/bold] {prompt}\n")

    effective_prompt = prompt
    if rag:
        rag_ctx = _try_retrieve_rag_context(prompt, top_k=5)
        if rag_ctx:
            effective_prompt = f"{rag_ctx}\n\nPipeline Goal: {prompt}"

    result = pipeline_engine.run(
        effective_prompt,
        max_turns_per_agent=max_turns,
        enable_thinking=thinking,
    )

    for idx, step in enumerate(result.steps, 1):
        rprint(Rule(f" Stage {idx}: {step.agent_name} ", style="bold green"))
        if step.tool_calls:
            rprint(f"[dim]Executed {len(step.tool_calls)} tool call(s):[/dim]")
            for tc in step.tool_calls:
                rprint(f"  [yellow]⚡ {tc.tool_name}[/yellow]({tc.arguments})")
        rprint(f"\n{step.content.strip()}\n")

    rprint(
        f"[bold green]✓ Multi-agent pipeline completed across {len(result.steps)} stage(s) "
        f"({result.total_turns} total turns, {len(result.all_tool_calls)} tool executions)."
        "[/bold green]"
    )
