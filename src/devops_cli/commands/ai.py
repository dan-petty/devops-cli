"""Manage AI provider configuration (Ollama, Claude, Copilot/OpenAI)."""

from __future__ import annotations

import math
import subprocess
from pathlib import Path
from typing import Annotated, Any

import typer

from devops_cli.ai.personas import Persona
from devops_cli.commands.ai_cache import app as cache_app
from devops_cli.commands.analyze import app as analyze_app
from devops_cli.commands.benchmark import app as benchmark_app
from devops_cli.commands.rag import app as rag_app
from devops_cli.commands.review import app as review_app
from devops_cli.config.constants import (
    CONST_AGENTS_MD_FILENAME,
    CONST_DEVCONTAINER_JSON_PATH,
    CONST_GIT_DIR_NAME,
)
from devops_cli.config.defaults import (
    DEFAULT_AI_PIPELINE_MAX_TURNS,
    DEFAULT_AI_PIPELINE_PERSONAS,
    DEFAULT_AI_PIPELINE_PROMPT,
    DEFAULT_AI_TEST_PROMPT,
    DEFAULT_DIFF_CHUNK_BUDGET,
    DEFAULT_ESTIMATED_PROMPT_TOKENS,
    DEFAULT_RAG_TOP_K,
    DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
    DEFAULT_TIKTOKEN_MODEL,
)
from devops_cli.config.env import env_var_for_option
from devops_cli.config.options import AI_API_KEY
from devops_cli.config.settings import (
    SecretStorageError,
    dotted_set,
    load_settings,
    save_settings,
)
from devops_cli.core.cli import new_typer
from devops_cli.core.process import run_subprocess
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import (
    escape_text,
    format_json,
    get_console,
    print_error,
    print_info,
    print_section,
    print_success,
    print_table,
    print_warning,
    write_stdout,
    write_text_file,
)

app = new_typer(
    help=HELP.ai.app,
    no_args_is_help=True,
)
app.add_typer(
    review_app,
    name="review",
    help=HELP.ai.review,
)
app.add_typer(
    analyze_app,
    name="analyze",
    help=HELP.ai.analyze,
)
app.add_typer(
    rag_app,
    name="rag",
    help=HELP.ai.rag,
)
app.add_typer(
    benchmark_app,
    name="benchmark",
    help=HELP.ai.benchmark,
)
app.add_typer(
    cache_app,
    name="cache",
    help=HELP.ai.cache,
)


@app.callback(invoke_without_command=True)
def ai_main(
    ctx: typer.Context,
    explain: Annotated[
        bool,
        typer.Option(
            "--explain",
            "-e",
            help=HELP.ai.explain_all,
        ),
    ] = False,
) -> None:
    """Manage AI provider configuration (Ollama, Claude, Copilot/OpenAI) and agent tools."""
    if explain:
        from devops_cli.ai.explain import render_explanation

        render_explanation("benchmark")
        raise typer.Exit(0)


# =============================================================================
# Constants & File Targets
# =============================================================================

_PROVIDERS = ("ollama", "claude", "copilot", "openai")

_AGENT_FILES: dict[str, str] = {
    CONST_AGENTS_MD_FILENAME: "Canonical agent instructions (single source of truth)",
    "CLAUDE.md": "Pointer stub redirecting Claude Code to AGENTS.md",
    ".github/copilot-instructions.md": "Pointer stub redirecting GitHub Copilot to AGENTS.md",
}


def _get_agents_task_addendum() -> str:
    from devops_cli.ai.task_loader import load_task_prompt

    return "\n" + load_task_prompt("generate_agents.md")


# =============================================================================
# Context Gathering & RAG Helpers
# =============================================================================


def _try_retrieve_rag_context(
    query: str,
    *,
    persona: str | None = None,
    category: str | None = None,
    project: str | None = None,
    top_k: int = DEFAULT_RAG_TOP_K,
) -> str | None:
    """Attempt to retrieve relevant semantic context from RAG vector store."""
    try:
        from devops_cli.ai.rag.investigator import investigate_rag_context

        ctx = investigate_rag_context(
            query,
            persona=persona,
            category=category,
            project=project,
            top_k=top_k,
        )
        if ctx and ctx.has_results:
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
        tree = run_subprocess(
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
    except OSError, subprocess.SubprocessError:
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
    rag_info = _try_retrieve_rag_context(
        f"project architecture design guidelines coding standards {target_file}",
        persona="architect",
        top_k=3,
    )
    rag_block = f"\n\n### Grounding Architectural Context:\n{rag_info}\n" if rag_info else ""
    return (
        f"Generate the contents of `{target_file}` for this project.\n\n"
        "The file must help AI coding assistants understand the project and work effectively.\n"
        "Include: project purpose, architecture overview, build/test/lint commands, "
        "code conventions, important file paths, security notes, and any non-obvious patterns.\n\n"
        f"{context}"
        f"{rag_block}"
    )


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


def _template_content(target_file: str, context_summary: dict[str, str] | Any) -> str:
    """Fallback template when no LLM is configured."""
    from devops_cli.ai.instruction_generator import (
        ProjectMetadata,
        generate_instruction_content,
    )

    if isinstance(context_summary, ProjectMetadata):
        meta = context_summary
    else:
        meta = ProjectMetadata(
            name=context_summary.get("name", "Project"),
            description=context_summary.get("description", ""),
            requires_python=context_summary.get("requires_python", ">=3.14"),
            entry_point=context_summary.get("entry_point", ""),
        )
    return generate_instruction_content(target_file, meta)


def _parse_pyproject(repo: Path) -> Any:
    """Extract structured fields from pyproject.toml and repo context."""
    from devops_cli.ai.instruction_generator import parse_project_metadata

    return parse_project_metadata(repo)


# =============================================================================
# Command: devops ai config
# =============================================================================


@app.command()
def config(
    provider: Annotated[
        str | None,
        typer.Option("--provider", "-p", help=f"Provider: {', '.join(_PROVIDERS)}"),
    ] = None,
    model: Annotated[
        str | None,
        typer.Option("--model", "-m", help=HELP.options.model),
    ] = None,
    ollama_urls: Annotated[
        str | None,
        typer.Option("--ollama-urls", help=HELP.ai.ollama_urls),
    ] = None,
    ollama_max_parallel: Annotated[
        int | None,
        typer.Option(
            "--ollama-max-parallel",
            help=HELP.ai.max_parallel,
        ),
    ] = None,
    api_base_url: Annotated[
        str | None,
        typer.Option("--api-base-url", help=HELP.ai.api_base_url),
    ] = None,
    api_key: Annotated[
        str | None,
        typer.Option("--api-key", help=HELP.ai.api_key),
    ] = None,
    max_retries: Annotated[
        int | None,
        typer.Option("--max-retries", help=HELP.ai.max_retries),
    ] = None,
) -> None:
    """Show or update AI provider configuration."""
    settings = load_settings()

    if not any(
        [
            provider,
            model,
            ollama_urls,
            ollama_max_parallel is not None,
            api_base_url,
            api_key,
            max_retries is not None,
        ]
    ):
        import os

        from devops_cli.config.options import KEYRING_KEYS
        from devops_cli.config.settings import _keyring_has

        ai = settings.ai
        has_key = bool(
            os.environ.get("DEVOPS_CLI_AI_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or _keyring_has(KEYRING_KEYS.get("ai.api_key", "ai_api_key"))
        )
        key_display = "[green]***set***[/green]" if has_key else "[dim](not set)[/dim]"
        rows = [
            ["provider", ai.provider],
            ["model", ai.model],
            ["ollama_urls", ", ".join(ai.get_ollama_urls)],
            ["ollama_max_parallel", str(ai.ollama_max_parallel)],
            ["api_base_url", ai.api_base_url or "(default)"],
            ["api_key", key_display],
            ["max_retries", str(ai.max_retries)],
        ]
        print_table(
            title="AI Configuration",
            columns=[("Setting", "cyan"), "Value"],
            rows=rows,
        )
        return

    if provider:
        if provider not in _PROVIDERS:
            print_error(
                f"Unknown provider {provider!r}. Choose: {', '.join(_PROVIDERS)}", prefix=False
            )
            raise typer.Exit(1)
        settings.ai.provider = provider
    if model:
        settings.ai.model = model
    if ollama_urls:
        settings.ai.ollama_urls = [u.strip() for u in ollama_urls.split(",") if u.strip()]
    if ollama_max_parallel is not None:
        settings.ai.ollama_max_parallel = max(1, ollama_max_parallel)
    if api_base_url:
        settings.ai.api_base_url = api_base_url
    if max_retries is not None:
        settings.ai.max_retries = max_retries
    if api_key:
        try:
            dotted_set(settings, AI_API_KEY, api_key)
            print_success("API key saved to keyring")
        except SecretStorageError as exc:
            print_error(f"Could not store ai.api_key: {exc}", prefix=False)
            env_var = env_var_for_option(AI_API_KEY)
            if env_var:
                print_warning(
                    f"Use environment variable fallback: export {env_var}=<value>",
                    prefix=False,
                )
            raise typer.Exit(1)

    save_settings(settings)
    print_success("AI configuration saved")


# =============================================================================
# Command: devops ai models
# =============================================================================


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
        print_error(f"Failed to list models: {exc}", prefix=False)
        raise typer.Exit(1)

    print_table(
        title=f"Available Models — {settings.ai.provider}",
        columns=[("Model", "cyan")],
        rows=[[m] for m in model_list],
    )


# =============================================================================
# Command: devops ai preload
# =============================================================================


@app.command()
def preload() -> None:
    """Preload configured model into VRAM across all configured Ollama servers."""
    from devops_cli.ai.client import LLMClient
    from devops_cli.config.settings import get_ai_api_key, load_settings

    settings = load_settings()
    if settings.ai.provider != "ollama":
        p = settings.ai.provider
        print_warning(f"Model preloading is for Ollama provider (current: {p}).", prefix=False)
        return
    client = LLMClient(settings.ai, api_key=get_ai_api_key(settings))
    print_info(
        f"Preloading model [bold cyan]{settings.ai.model}[/bold cyan] across Ollama nodes...",
        prefix=False,
    )
    results = client.preload_models()
    for url, ok in results.items():
        status = "[green]✓ preloaded[/green]" if ok else "[red]✗ failed[/red]"
        print_info(f"  {url}: {status}", prefix=False)


# =============================================================================
# Command: devops ai test
# =============================================================================


def _test_single_ollama_endpoint(
    u: str, test_sys_prompt: str, prompt: str, settings: Any
) -> tuple[str, bool, str, str]:
    """Execute test chat prompt against a specific Ollama endpoint URL."""
    from devops_cli.ai.client import LLMClient
    from devops_cli.config.settings import get_ai_api_key

    sub_cfg = settings.ai.model_copy(update={"ollama_urls": [u]})
    sub_client = LLMClient(sub_cfg, api_key=get_ai_api_key(settings))
    try:
        resp = sub_client.chat(system=test_sys_prompt, user=prompt)
        wall_sec = (
            f"{resp.wall_seconds:.2f}s"
            if getattr(resp, "wall_seconds", None) is not None
            else "0.0s"
        )
        return (u, True, str(resp).strip(), wall_sec)
    except Exception as exc:
        return (u, False, str(exc), "0.0s")


def _print_chat_thought(th: str) -> None:
    """Print thinking block stream during interactive chat."""
    print_info(
        f"\n[dim cyan]💭 Thinking...[/dim cyan]\n"
        f"[dim italic]{escape_text(th)}[/dim italic]\n"
        f"[dim cyan]✓ Thought complete[/dim cyan]\n",
        prefix=False,
    )


def _print_chat_tool(t_name: str, t_args: dict[str, Any], t_res: Any) -> None:
    """Print tool invocation and result during interactive chat."""
    args_str = ", ".join(f"{k}={v!r}" for k, v in t_args.items())
    if len(args_str) > 60:
        args_str = args_str[:57] + "..."
    print_info(
        f"\n[dim yellow]🔧 Tool: [bold]{t_name}[/bold]({args_str})[/dim yellow]", prefix=False
    )
    res_str = str(t_res).strip()
    if len(res_str) > 200:
        res_str = res_str[:197] + "..."
    print_info(f"[dim green]✓ Result: {res_str}[/dim green]\n", prefix=False)


def _run_ollama_server_tests(
    urls: list[str], test_sys_prompt: str, prompt: str, settings: Any
) -> None:
    """Execute parallel tests against multiple Ollama endpoints."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    all_passed = True
    with ThreadPoolExecutor(max_workers=len(urls)) as executor:
        futures = {
            executor.submit(_test_single_ollama_endpoint, u, test_sys_prompt, prompt, settings): u
            for u in urls
        }
        for f in as_completed(futures):
            u, ok, ans, wall = f.result()
            if ok:
                print_info(
                    MESSAGES.ai.ollama_endpoint_pass.format(url=u, ans=ans, wall=wall), prefix=False
                )
            else:
                all_passed = False
                print_error(MESSAGES.ai.ollama_endpoint_fail.format(url=u, ans=ans), prefix=False)

    if not all_passed:
        raise typer.Exit(1)


@app.command()
def test(
    prompt: Annotated[
        str,
        typer.Option("--prompt", "-p", help=HELP.ai.prompt),
    ] = DEFAULT_AI_TEST_PROMPT,
    url: Annotated[
        str | None,
        typer.Option("--url", "-u", help=HELP.ai.url),
    ] = None,
) -> None:
    """Send a test prompt to verify AI provider connectivity across configured servers."""
    from devops_cli.ai.client import LLMClient
    from devops_cli.ai.task_loader import load_task_prompt
    from devops_cli.config.settings import get_ai_api_key, load_settings

    settings = load_settings()
    test_sys_prompt = load_task_prompt("test_assistant.md")

    if settings.ai.provider == "ollama":
        urls = [url] if url else settings.ai.get_ollama_urls
        if len(urls) > 1:
            print_info(
                MESSAGES.ai.testing_ollama_servers.format(count=len(urls), model=settings.ai.model),
                prefix=False,
            )
            _run_ollama_server_tests(urls, test_sys_prompt, prompt, settings)
            return

    client = LLMClient(settings.ai, api_key=get_ai_api_key(settings))
    print_info(
        f"Testing provider: [cyan]{client.backend_info}[/cyan] | "
        f"model: [cyan]{settings.ai.model}[/cyan]...",
        prefix=False,
    )
    try:
        resp = client.chat(system=test_sys_prompt, user=prompt)
        handled = getattr(resp, "backend_info", None) or client.backend_info
        wall_sec = (
            f" in {resp.wall_seconds:.1f}s"
            if getattr(resp, "wall_seconds", None) is not None
            else ""
        )
        print_success(f"{str(resp).strip()} [dim](handled by {handled}{wall_sec})[/dim]")
    except Exception as exc:
        print_error(f"AI provider test failed: {exc}", prefix=False)
        raise typer.Exit(1)


# =============================================================================
# Command: devops ai agents
# =============================================================================


@app.command()
def agents(
    repo: Annotated[
        Path,
        typer.Option("--repo", "-r", help=HELP.options.repo),
    ] = Path("."),
    template: Annotated[
        bool,
        typer.Option("--template", help=HELP.ai.template),
    ] = False,
    files: Annotated[
        list[str],
        typer.Option("--file", "-f", help=HELP.ai.generate_file),
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
            print_warning(f"LLM unavailable ({exc}), falling back to template.", prefix=False)
            use_llm = False

    for target in files:
        from devops_cli.lang import MESSAGES

        dest = (repo / target).resolve()
        repo_resolved = repo.resolve()
        if not (dest == repo_resolved or dest.is_relative_to(repo_resolved)):
            msg = MESSAGES.messages.target_path_outside_repo.format(dest=dest)
            print_error(msg, prefix=False)
            continue
        print_section(f" {target} ", style="cyan")

        # Only the canonical file is worth spending an LLM call on — the others
        # are static pointers to it, so they always use the template.
        if target != CONST_AGENTS_MD_FILENAME:
            content = _template_content(target, meta)
        elif use_llm and client is not None:
            from devops_cli.ai.personas import PERSONAS, Persona

            print_info(
                MESSAGES.ai.generating_agents.format(target=f"[cyan]{target}[/cyan]"), prefix=False
            )
            system = PERSONAS[Persona.ARCHITECT].system_prompt + _get_agents_task_addendum()
            try:
                content = client.chat(
                    system=system,
                    user=_agent_prompt(context, target),
                )
            except Exception as exc:
                msg = MESSAGES.messages.llm_failed_template_fallback.format(exc=exc)
                print_warning(msg, prefix=False)
                content = _template_content(target, meta)
        else:
            content = _template_content(target, meta)

        if not content.endswith("\n"):
            content += "\n"
        write_text_file(dest, content)
        print_info(MESSAGES.ai.written_file.format(path=dest.relative_to(repo)), prefix=False)


_PERSONA_NAMES = [p.value for p in Persona]


def _stream_interactive_chat_turn(
    client: Any,
    agent: Any,
    thinking: bool,
    effective_prompt: str,
) -> None:
    """Execute streaming response with live thinking and output filtering."""
    from devops_cli.ai.thinking_stream import ThinkingStreamProcessor, strip_think_blocks

    processor = ThinkingStreamProcessor(
        show_thinking=thinking,
        console=get_console(),
    )
    system_with_tools = agent._build_system_prompt_with_tools()
    messages = agent.memory.to_chat_messages()
    for chunk in client.chat_messages_stream(system_with_tools, messages, enable_thinking=thinking):
        processor.feed(chunk)
    processor.flush()
    reply = processor.clean_content
    if not reply.strip() and processor.thinking_content:
        # Model put all output in thinking tags; retrieve summary
        agent_res = agent.run(effective_prompt, enable_thinking=thinking)
        reply = strip_think_blocks(agent_res.content)
        if reply.strip():
            print_info(f"{reply.strip()}\n", prefix=False)
        return
    write_stdout("\n\n")
    agent.memory.add_interaction("assistant", reply)


# =============================================================================
# Command: devops ai chat
# =============================================================================


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
            help=HELP.ai.context_file,
            exists=True,
            readable=True,
        ),
    ] = None,
    rag: Annotated[bool, typer.Option("--rag/--no-rag", help=HELP.ai.rag_context)] = True,
    stream: Annotated[bool, typer.Option("--stream/--no-stream", help=HELP.ai.stream)] = True,
    tools: Annotated[bool, typer.Option("--tools/--no-tools", help=HELP.ai.tools)] = True,
    thinking: Annotated[
        bool, typer.Option("--thinking/--no-thinking", help=HELP.ai.thinking)
    ] = True,
    prewarm: Annotated[bool, typer.Option("--prewarm/--no-prewarm", help=HELP.ai.prewarm)] = True,
    explain: Annotated[
        bool,
        typer.Option("--explain", "-e", help=HELP.ai.explain_chat),
    ] = False,
) -> None:
    """Start an interactive chat with a Pydantic AI persona (tools, thinking, streaming, RAG)."""
    if explain:
        from devops_cli.ai.explain import render_explanation

        render_explanation("rag")
        return
    import sys

    from devops_cli.ai.agents import PydanticAgent
    from devops_cli.ai.client import LLMClient
    from devops_cli.ai.tools import get_persona_tools
    from devops_cli.config.settings import get_ai_api_key, load_settings

    if persona not in _PERSONA_NAMES:
        print_error(
            f"Unknown persona {persona!r}. Choose: {', '.join(_PERSONA_NAMES)}", prefix=False
        )
        raise typer.Exit(1)

    from devops_cli.ai.personas import PERSONAS, Persona

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
            print_info(
                f"[dim]Prewarming model '{settings.ai.model}' in background across "
                f"{n_nodes} node(s)...[/dim]",
                prefix=False,
            )
            client.preload_models(blocking=False)

    agent_tools = get_persona_tools(persona) if tools else []
    agent: PydanticAgent[Any] = PydanticAgent(
        client=client, system_prompt=system, tools=agent_tools
    )

    print_section(
        f" [cyan]{persona_def.title}[/cyan] (Pydantic Agent)  "
        f"[dim]{client.backend_info} / {settings.ai.model}[/dim] ",
        style="cyan",
    )
    print_info(
        "[dim]Type your message and press Enter. Ctrl+C or [bold]exit[/bold] to quit.[/dim]\n",
        prefix=False,
    )

    while True:
        try:
            user_input = get_console().input("[bold cyan]You:[/bold cyan] ").strip()
        except EOFError, KeyboardInterrupt:
            from devops_cli.lang import MESSAGES

            print_info(f"\n[dim]{MESSAGES.messages.goodbye}[/dim]", prefix=False)
            break

        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit", "/exit", "/quit"}:
            print_info("[dim]Goodbye.[/dim]", prefix=False)
            break

        effective_prompt = user_input
        if rag:
            rag_snippet = _try_retrieve_rag_context(user_input, persona=persona, top_k=3)
            if rag_snippet:
                effective_prompt = f"{rag_snippet}\n\nUser Question: {user_input}"

        try:
            write_stdout(f"\n{persona_def.title}: ")
            sys.stdout.flush()

            from devops_cli.ai.thinking_stream import strip_think_blocks

            if stream and not tools:
                _stream_interactive_chat_turn(client, agent, thinking, effective_prompt)
            else:
                agent_res = agent.run(
                    effective_prompt,
                    enable_thinking=thinking,
                    on_thought=_print_chat_thought if thinking else None,
                    on_tool_call=_print_chat_tool,
                )

                reply = strip_think_blocks(agent_res.content)
                if reply.strip():
                    print_info(f"{reply.strip()}\n", prefix=False)

        except KeyboardInterrupt:
            print_info("\n[dim]Interrupted.[/dim]\n", prefix=False)
        except Exception as exc:
            print_error(f"\nError: {exc}\n", prefix=False)
            if agent.memory.entries:
                agent.memory.entries.pop()  # don't add failed turn to history
            continue

        if agent.memory.auto_summarize_if_needed(llm_client=client):
            print_info(
                "[dim]⚡ Long conversation memory consolidated into context summary.[/dim]",
                prefix=False,
            )


# =============================================================================
# Command: devops ai bundle-models
# =============================================================================


@app.command("bundle-models")
def bundle_models(
    output_dir: Annotated[
        Path | None,
        typer.Option("--output", "-o", help=HELP.options.output_dir),
    ] = None,
) -> None:
    """Bundle Ollama model metadata into tarball for air-gapped DevContainers."""
    from devops_cli.ai.model_bundler import bundle_ollama_models

    count, manifest_path = bundle_ollama_models(output_dir=output_dir)
    print_success(f"Bundled {count} model(s) → [bold]{manifest_path}[/bold]")


# =============================================================================
# Command: devops ai pipeline
# =============================================================================


@app.command("pipeline")
def pipeline(
    prompt: Annotated[
        str,
        typer.Argument(
            help=HELP.ai.goal,
        ),
    ] = DEFAULT_AI_PIPELINE_PROMPT,
    personas: Annotated[
        str,
        typer.Option(
            "--personas",
            "-p",
            help=HELP.ai.personas_seq,
        ),
    ] = DEFAULT_AI_PIPELINE_PERSONAS,
    max_turns: Annotated[
        int,
        typer.Option("--max-turns", help=HELP.ai.max_turns),
    ] = DEFAULT_AI_PIPELINE_MAX_TURNS,
    rag: Annotated[bool, typer.Option("--rag/--no-rag", help=HELP.ai.rag_context)] = True,
    thinking: Annotated[
        bool,
        typer.Option("--thinking/--no-thinking", help=HELP.ai.thinking),
    ] = True,
) -> None:
    """Run a multi-agent Pydantic pipeline with shared DevOps tools and RAG context."""
    from devops_cli.ai.agents import PydanticAgent
    from devops_cli.ai.agents.pipeline import MultiAgentPipeline
    from devops_cli.ai.client import LLMClient
    from devops_cli.ai.personas import PERSONAS, Persona
    from devops_cli.ai.tools import get_default_tools, get_persona_tools
    from devops_cli.config.settings import get_ai_api_key, load_settings
    from devops_cli.dry_run import is_dry_run
    from devops_cli.output import render_dry_run_result

    persona_names = [p.strip().lower() for p in personas.split(",") if p.strip()]
    valid_personas: list[Persona] = []
    for name in persona_names:
        if name not in _PERSONA_NAMES:
            print_error(
                f"Unknown persona {name!r}. Choose from: {', '.join(_PERSONA_NAMES)}", prefix=False
            )
            raise typer.Exit(1)
        valid_personas.append(Persona(name))

    if is_dry_run():
        render_dry_run_result(
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

    print_section(
        f" [cyan]Multi-Agent Pipeline ({len(valid_personas)} Stages)[/cyan]  "
        f"[dim]{client.backend_info}[/dim] ",
        style="cyan",
    )
    print_info(f"[bold]Initial Prompt:[/bold] {prompt}\n", prefix=False)

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
        print_section(f" Stage {idx}: {step.agent_name} ", style="bold green")
        if step.tool_calls:
            print_info(f"[dim]Executed {len(step.tool_calls)} tool call(s):[/dim]", prefix=False)
            for tc in step.tool_calls:
                print_info(f"  [yellow]⚡ {tc.tool_name}[/yellow]({tc.arguments})", prefix=False)
        print_info(f"\n{step.content.strip()}\n", prefix=False)

    print_success(
        f"Multi-agent pipeline completed across {len(result.steps)} stage(s) "
        f"({result.total_turns} total turns, {len(result.all_tool_calls)} tool executions)."
    )


# =============================================================================
# Command: devops ai token-count
# =============================================================================


@app.command("token-count")
def token_count(
    target: Annotated[
        str | None,
        typer.Argument(help=HELP.ai.token_target),
    ] = None,
    model: Annotated[
        str,
        typer.Option("--model", "-m", help=HELP.options.model),
    ] = DEFAULT_TIKTOKEN_MODEL,
    budget: Annotated[
        int,
        typer.Option("--budget", "-b", help=HELP.ai.budget),
    ] = DEFAULT_DIFF_CHUNK_BUDGET,
    json_output: Annotated[
        bool,
        typer.Option("--json", help=HELP.options.json_output),
    ] = False,
) -> Any:
    """Calculate exact BPE tokens for text or files using tiktoken context budgeting."""
    from devops_cli.ai.context_budget import TokenBudgetReport, count_file_tokens, count_tokens

    content = target or ""
    p = Path(content)
    if p.exists() and p.is_file():
        num_tokens = count_file_tokens(p, model=model)
        raw_len = len(p.read_text(encoding="utf-8", errors="replace"))
        desc = f"File: {p}"
    else:
        num_tokens = count_tokens(content, model=model)
        raw_len = len(content)
        desc = f"Text snippet ({raw_len} chars)"

    fits = num_tokens <= budget
    report = TokenBudgetReport(
        text_length=raw_len,
        estimated_tokens=num_tokens,
        max_budget=budget,
        fits_budget=fits,
        model=model,
        chunk_count=max(1, math.ceil(num_tokens / max(1, budget))),
    )

    if json_output:
        write_stdout(format_json(report.model_dump()) + "\n")
        return report

    rows = [
        ["Target", desc],
        ["Model Encoding", model],
        ["Character Length", str(raw_len)],
        ["Estimated Tokens", str(num_tokens)],
        ["Token Budget Limit", str(budget)],
        [
            "Fits Budget",
            MESSAGES.ai.fits_budget_yes if fits else MESSAGES.ai.fits_budget_no,
        ],
    ]

    print_table(
        title=MESSAGES.ai.token_budget_title,
        columns=[("Property", "bold"), ("Value", "green" if fits else "red")],
        rows=rows,
        border_style="cyan",
    )
    return report


# =============================================================================
# Command: devops ai route
# =============================================================================


@app.command("route")
def route_task(
    task: Annotated[str, typer.Argument(help=HELP.ai.cost_task)],
    tokens: Annotated[
        int, typer.Option("--tokens", "-t", help=HELP.ai.est_tokens)
    ] = DEFAULT_ESTIMATED_PROMPT_TOKENS,
    frontier: Annotated[bool, typer.Option("--frontier", "-f", help=HELP.options.frontier)] = False,
    json_output: Annotated[bool, typer.Option("--json", help=HELP.options.json_output)] = False,
) -> None:
    """Evaluate task complexity and determine the optimal LLM provider and model route."""
    from devops_cli.ai.router import LLMRouter
    from devops_cli.config.settings import load_settings

    settings = load_settings()
    router = LLMRouter(config=settings.ai)
    decision = router.route_task(
        task_name=task,
        token_count=tokens,
        requires_frontier=frontier,
    )

    if json_output:
        write_stdout(format_json(decision.model_dump()) + "\n")
        return

    rows = [
        ["Task Name", decision.task_name],
        ["Complexity Tier", str(decision.complexity).upper()],
        ["Selected Provider", decision.provider_name],
        ["Target Model", decision.model_name],
        ["Est. Turn Cost (USD)", f"${decision.estimated_cost_usd:.4f}"],
        ["Routing Rationale", decision.rationale],
    ]

    print_table(
        title="AI Task Dynamic Routing Decision",
        columns=[("Property", "bold"), "Value"],
        rows=rows,
        border_style="magenta",
    )


# =============================================================================
# Command: devops ai spec
# =============================================================================


@app.command("spec")
def spec_verify_cmd(
    spec_path: Annotated[
        Path | None,
        typer.Argument(help="Path to markdown architecture specification contract"),
    ] = None,
    target_dir: Annotated[
        Path | None,
        typer.Option("--target", "-t", help="Target source directory to verify"),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Simulate architecture spec verification"),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output specification verification report as JSON"),
    ] = False,
) -> None:
    """Verify codebase against executable markdown architecture specification contracts."""
    from devops_cli.ai.spec import verify_architecture_spec
    from devops_cli.dry_run import is_dry_run

    report = verify_architecture_spec(
        spec_path=spec_path,
        target_dir=target_dir,
        dry_run=dry_run,
    )

    if dry_run or is_dry_run():
        return

    if json_output:
        write_stdout(format_json(report.model_dump()) + "\n")
        return

    if report.failed_rules == 0:
        print_success(
            f"✓ Architecture specification verified: {report.passed_rules} invariants satisfied."
        )
        return

    rows = []
    for r in report.rule_results:
        st_style = "green" if r.passed else "bold red"
        st_text = "PASS" if r.passed else "FAIL"
        rows.append([r.name, r.target_path, f"[{st_style}]{st_text}[/{st_style}]", r.details])

    print_table(
        title=f"Architecture Spec Invariants: {report.spec_name}",
        columns=["Rule", "Location", "Status", "Details"],
        rows=rows,
        border_style="red",
    )
    raise typer.Exit(1)


# =============================================================================
# Command: devops ai repomap
# =============================================================================


@app.command("repomap")
def repomap_cmd(
    target_dir: Annotated[
        Path | None,
        typer.Option(
            "--target", "-t", "--dir", "-d", help="Target root directory to generate symbol map for"
        ),
    ] = None,
    max_files: Annotated[
        int,
        typer.Option("--max-files", "-n", help="Maximum source files to include"),
    ] = 100,
    include_tests: Annotated[
        bool,
        typer.Option("--include-tests", help="Include test modules in symbol map"),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help=HELP.options.json_output),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Generate compact whole-repository AST symbol and relationship map."""
    import json

    from devops_cli.ai.repomap import generate_repo_map, render_repo_map_text
    from devops_cli.dry_run import is_dry_run, render_dry_run_result

    if dry_run or is_dry_run():
        render_dry_run_result(
            command="devops ai repomap",
            action="generate_symbol_map",
            details={
                "max_files": max_files,
                "include_tests": include_tests,
                "status": "DRY_RUN_MAPPED",
            },
        )
        return

    maps = generate_repo_map(target_dir, max_files=max_files, include_tests=include_tests)
    if json_output:
        payload = {"files_count": len(maps), "files": [f.to_dict() for f in maps]}
        write_stdout(json.dumps(payload, indent=2) + "\n")
        return

    text = render_repo_map_text(maps)
    print_info(
        f"[bold]Repository AST Symbol Map[/bold] ({len(maps)} files mapped):\n",
        prefix=False,
    )
    write_stdout(text + "\n")


# =============================================================================
# Command: devops ai diagram
# =============================================================================


@app.command("diagram")
def diagram_cmd(
    diagram_type: Annotated[
        str,
        typer.Argument(
            help="Diagram type: 'arch' for architecture topology, 'threat' for STRIDE model"
        ),
    ] = "arch",
    target_dir: Annotated[
        Path | None,
        typer.Option("--target", "-t", "--dir", "-d", help="Target root directory to analyze"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help=HELP.options.json_output),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Generate visual Mermaid architecture topology or STRIDE threat modeling diagrams."""
    import json

    from devops_cli.ai.diagram import generate_architecture_diagram, generate_threat_diagram
    from devops_cli.dry_run import is_dry_run, render_dry_run_result

    if dry_run or is_dry_run():
        render_dry_run_result(
            command=f"devops ai diagram {diagram_type}",
            action="generate_diagram",
            details={"type": diagram_type, "status": "DRY_RUN_DIAGRAM_GENERATED"},
        )
        return

    if diagram_type.lower() == "threat":
        diag = generate_threat_diagram(target_dir)
    else:
        diag = generate_architecture_diagram(target_dir)

    if json_output:
        write_stdout(json.dumps(diag.to_dict(), indent=2) + "\n")
        return

    print_info(f"[bold]{diag.title}[/bold] (Mermaid Diagram):\n", prefix=False)
    write_stdout(f"```mermaid\n{diag.mermaid_code}\n```\n")


# =============================================================================
# Command: devops ai prompt-eval
# =============================================================================


@app.command("prompt-eval")
def prompt_eval_cmd(
    persona: Annotated[
        str,
        typer.Option("--persona", "-p", help="Review persona to benchmark"),
    ] = "devsecops",
    dataset: Annotated[
        Path | None,
        typer.Option("--dataset", "-d", help="Path to feedback dataset jsonl"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help=HELP.options.json_output),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Benchmark persona prompt variations against verified review feedback datasets."""
    import json

    from devops_cli.ai.prompt_eval import evaluate_persona_prompts
    from devops_cli.dry_run import is_dry_run, render_dry_run_result

    if dry_run or is_dry_run():
        render_dry_run_result(
            command="devops ai prompt-eval",
            action="benchmark_prompts",
            details={"persona": persona, "status": "BENCHMARK_DRY_RUN"},
        )
        return

    res = evaluate_persona_prompts(persona=persona, dataset_path=dataset)
    if json_output:
        write_stdout(json.dumps(res.to_dict(), indent=2) + "\n")
        return

    print_info(
        f"[bold]Prompt Mutation Benchmark — Persona: {res.persona}[/bold] (Cases: {res.total_cases})",
        prefix=False,
    )
    print_table(
        columns=["Metric", "Result"],
        rows=[
            ["Total Test Cases", str(res.total_cases)],
            ["Verified Matches", str(res.verified_matches)],
            ["Invalid Rejections", str(res.invalidated_rejections)],
            ["False Positive Rate", f"{res.false_positive_rate:.1%}"],
            ["Accuracy Score", f"[green]{res.accuracy_score:.1%}[/green]"],
        ],
        border_style="cyan",
    )


# =============================================================================
# Command: devops ai test-gen
# =============================================================================


@app.command("test-gen")
def test_gen_cmd(
    target_file: Annotated[
        Path,
        typer.Argument(help="Target source file to synthesize unit tests for"),
    ],
    function_name: Annotated[
        str | None,
        typer.Option("--function", "-f", help="Specific function to synthesize tests for"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help=HELP.options.json_output),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Synthesize isolated pytest unit test suites for functions or source files."""
    import json

    from devops_cli.ai.test_gen import synthesize_unit_tests
    from devops_cli.dry_run import is_dry_run, render_dry_run_result

    if dry_run or is_dry_run():
        render_dry_run_result(
            command="devops ai test-gen",
            action="synthesize_unit_tests",
            details={
                "target_file": str(target_file),
                "function": function_name,
                "status": "SYNTHESIZED_DRY_RUN",
            },
        )
        return

    res = synthesize_unit_tests(target_file, function_filter=function_name)
    if json_output:
        write_stdout(json.dumps(res.to_dict(), indent=2) + "\n")
        return

    print_success(f"✓ Synthesized {res.test_count} unit test(s) for {res.target_file}:")
    write_stdout(f"```python\n{res.test_code}\n```\n")
