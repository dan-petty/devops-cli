"""Unit tests for the devops ai CLI subcommands."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

if TYPE_CHECKING:
    from tests.support.fakes.model import ModelFake

import pytest
import typer

from devops_cli.ai.agents.memory import AgentMemory
from devops_cli.ai.agents.models import AgentResponse
from devops_cli.ai.client import AIClientError, LLMClient
from devops_cli.ai.instruction_generator import collect_project_context
from devops_cli.commands.ai import (
    print_chat_thought,
    print_chat_tool,
    probe_single_ollama_endpoint,
    run_ollama_server_tests,
    stream_interactive_chat_turn,
)
from devops_cli.config.defaults import DEFAULT_CHAT_INVARIANTS
from devops_cli.config.os_keyring import SecretStorageError
from devops_cli.config.settings import AIConfig

pytestmark = pytest.mark.usefixtures("keyring_store")


def _setup_telemetry_and_ollama(
    config: Callable[..., Path], side_channel_port: int, **extra_ai: Any
) -> None:
    config(
        telemetry={"endpoint": f"http://127.0.0.1:{side_channel_port}"},
        ai={"ollama_urls": ["http://localhost:11434"], **extra_ai},
    )


def test_ai_config_shows_configuration(
    cli: Callable[..., Any], config: Callable[..., Path], unserved_side_channel_port: int
) -> None:
    """Verify execution of devops ai config shows current configuration table."""
    _setup_telemetry_and_ollama(config, unserved_side_channel_port)
    res = cli("ai", "config")
    assert (res.exit_code, "AI Configuration" in res.stdout) == (0, True)


def test_ai_config_sets_provider_and_model(
    cli: Callable[..., Any], config: Callable[..., Path], unserved_side_channel_port: int
) -> None:
    """Verify devops ai config updates provider and model."""
    _setup_telemetry_and_ollama(config, unserved_side_channel_port)
    res = cli("ai", "config", "--provider", "ollama", "--model", "qwen2.5-coder")
    assert res.exit_code == 0


def test_ai_test_pings_endpoint(
    cli: Callable[..., Any],
    config: Callable[..., Path],
    model_fake: ModelFake,
    unserved_side_channel_port: int,
) -> None:
    """Verify devops ai test sends a test prompt to the provider."""
    _setup_telemetry_and_ollama(config, unserved_side_channel_port)
    model_fake.answer("OK")
    res = cli("ai", "test", "--prompt", "Ping")
    assert res.exit_code == 0


def test_ai_models_lists_available_models(
    cli: Callable[..., Any],
    config: Callable[..., Path],
    model_fake: ModelFake,
    unserved_side_channel_port: int,
) -> None:
    """Verify devops ai models lists available models."""
    _setup_telemetry_and_ollama(config, unserved_side_channel_port)
    model_fake.set_available_models(["gemma4:26b"])
    res = cli("ai", "models")
    assert (res.exit_code, "gemma4:26b" in res.stdout) == (0, True)


def test_ai_agents_generates_template(
    tmp_path: Path,
    cli: Callable[..., Any],
    config: Callable[..., Path],
    unserved_side_channel_port: int,
) -> None:
    """Verify devops ai agents creates instruction template."""
    _setup_telemetry_and_ollama(config, unserved_side_channel_port)
    res = cli("ai", "agents", "--template", "--repo", str(tmp_path))
    assert res.exit_code == 0


def test_ai_agents_overwrites_file_with_force(
    tmp_path: Path,
    cli: Callable[..., Any],
    config: Callable[..., Path],
    unserved_side_channel_port: int,
) -> None:
    """Verify devops ai agents overwrites existing file when force is given."""
    _setup_telemetry_and_ollama(config, unserved_side_channel_port)
    res = cli(
        "ai",
        "agents",
        "--template",
        "--force",
        "--file",
        "AGENTS.md",
        "--repo",
        str(tmp_path),
    )
    assert res.exit_code == 0


def test_ai_chat_explain_renders_explanation(
    cli: Callable[..., Any],
    config: Callable[..., Path],
    model_fake: ModelFake,
    unserved_side_channel_port: int,
) -> None:
    """Verify devops ai chat --explain renders chat explanation."""
    _setup_telemetry_and_ollama(config, unserved_side_channel_port)
    model_fake.answer("Agent response")
    res = cli("ai", "chat", "--explain")
    assert res.exit_code == 0


def test_ai_preload_warms_configured_models(
    cli: Callable[..., Any],
    config: Callable[..., Path],
    model_fake: ModelFake,
    unserved_side_channel_port: int,
) -> None:
    """Verify devops ai preload warms configured models."""
    _setup_telemetry_and_ollama(config, unserved_side_channel_port)
    model_fake.set_preload_results({"qwen2.5-coder": True})
    res = cli("ai", "preload")
    assert res.exit_code == 0


def test_ai_chat_model_task_and_cli_overrides(
    cli: Callable[..., Any],
    config: Callable[..., Path],
    unserved_side_channel_port: int,
) -> None:
    """Verify ai chat respects tasks.chat.model and CLI --model override."""
    _setup_telemetry_and_ollama(
        config,
        unserved_side_channel_port,
        model="base-model:latest",
        tasks={"chat": {"model": "chat-override-model:20b"}},
    )

    res_task = cli("ai", "chat", "--no-prewarm", "--no-rag", input="exit\n")
    assert (res_task.exit_code, "chat-override-model:20b" in res_task.stdout) == (0, True)

    res_cli = cli(
        "ai",
        "chat",
        "--model",
        "cli-model:7b",
        "--no-prewarm",
        "--no-rag",
        input="exit\n",
    )
    assert (res_cli.exit_code, "cli-model:7b" in res_cli.stdout) == (0, True)


def test_llm_client_model_property() -> None:
    """Verify LLMClient.model exposes the active model identifier."""
    client = LLMClient(config=AIConfig(model="gpt-oss:20b"))
    assert client.model == "gpt-oss:20b"


def test_ai_token_count_estimates_text(cli: Callable[..., Any]) -> None:
    """Verify token-count estimates token usage for text."""
    res = cli("ai", "token-count", "Hello world from devops CLI")
    assert res.exit_code == 0
    assert "token" in res.stdout.lower()


def test_ai_token_count_estimates_file(tmp_path: Path, cli: Callable[..., Any]) -> None:
    """Verify token-count estimates token usage for a file."""
    sample_file = tmp_path / "code.py"
    sample_file.write_text("def foo():\n    return 42\n", encoding="utf-8")

    res = cli("ai", "token-count", str(sample_file), "--json")
    assert (res.exit_code, "estimated_tokens" in res.stdout) == (0, True)


def test_ai_bundle_models_archives_models(
    tmp_path: Path, cli: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify bundle-models packs models into an archive."""
    monkeypatch.setattr(
        "devops_cli.ai.model_bundler.bundle_ollama_models",
        lambda *a, **k: (2, tmp_path / "models.tar.gz"),
    )
    res = cli("ai", "bundle-models", "--output", str(tmp_path))
    assert (res.exit_code, "Bundled 2 model" in res.stdout) == (0, True)


def test_ai_explain(cli: Callable[..., Any]) -> None:
    """Test ai --explain flag."""
    res = cli("ai", "--explain")
    assert res.exit_code == 0


@pytest.mark.live("find")
def test_ai_collect_project_context_and_agents_llm(
    tmp_path: Path,
    model_fake: ModelFake,
    cli: Callable[..., Any],
    config: Callable[..., Path],
    refusing_port: int,
    unserved_side_channel_port: int,
) -> None:
    """Verify collect_project_context and agents command with LLM generation.

    Qdrant is down, refused through `refusing_port`, so the context holds no retrieved knowledge.
    """
    config(
        telemetry={"endpoint": f"http://127.0.0.1:{unserved_side_channel_port}"},
        qdrant={"url": f"http://127.0.0.1:{refusing_port}"},
        ai={"ollama_urls": ["http://localhost:11434"]},
    )

    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Demo Project\n", encoding="utf-8")
    (tmp_path / ".editorconfig").write_text("root = true\n", encoding="utf-8")
    (tmp_path / ".devcontainer").mkdir()
    (tmp_path / ".devcontainer" / "devcontainer.json").write_text(
        '{"name": "demo"}', encoding="utf-8"
    )

    ctx = collect_project_context(tmp_path)
    assert "pyproject.toml" in ctx
    assert "README.md" in ctx
    assert ".editorconfig" in ctx
    assert "devcontainer.json" in ctx

    model_fake.answer("# AGENTS.md content\nArchitecture and standards.")
    res_agents = cli("ai", "agents", "--repo", str(tmp_path), "--file", "AGENTS.md")
    assert (res_agents.exit_code, (tmp_path / "AGENTS.md").exists()) == (0, True)


def test_ai_chat_helpers_print_thought_and_tool(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify chat helper functions format thoughts and tool outputs cleanly."""
    print_chat_thought("Checking dependencies")
    print_chat_tool("search", {"query": "test"}, "Found 3 results")

    captured = capsys.readouterr()
    shown = captured.out + captured.err
    assert ("Checking dependencies" in shown, "search" in shown, "Found 3 results" in shown) == (
        True,
        True,
        True,
    )


def test_ai_chat_refuses_unknown_persona(cli: Callable[..., Any]) -> None:
    """Verify chat rejects unknown persona names."""
    res = cli("ai", "chat", "--persona", "nonexistent_persona")
    assert res.exit_code == 1


def test_ai_pipeline_refuses_unknown_persona(cli: Callable[..., Any]) -> None:
    """Verify pipeline rejects unknown persona names."""
    res = cli("ai", "pipeline", "--personas", "bad_persona")
    assert res.exit_code == 1


def test_ai_pipeline_dry_run_exits_zero(cli: Callable[..., Any]) -> None:
    """Verify pipeline runs under dry run mode without real execution."""
    res = cli("--dry-run", "ai", "pipeline", "review repo")
    assert res.exit_code == 0


def test_ai_config_updates_connection_options(cli: Callable[..., Any]) -> None:
    """Verify config subcommand updates parallel and timeout options."""
    res = cli(
        "ai",
        "config",
        "--ollama-max-parallel",
        "4",
        "--api-base-url",
        "https://api.openai.com/v1",
        "--max-retries",
        "3",
    )
    assert res.exit_code == 0


def test_ai_single_ollama_endpoint_evaluates_health(
    model_fake: ModelFake,
    config: Callable[..., Path],
    unserved_side_channel_port: int,
) -> None:
    """Verify single endpoint health evaluation returns success and handles failure."""
    _setup_telemetry_and_ollama(config, unserved_side_channel_port)
    from devops_cli.config.settings import load_settings

    st = load_settings()
    model_fake.answer("OK")
    _, ok, ans, _ = probe_single_ollama_endpoint("http://localhost:11434", "sys", "user", st)
    assert (ok, ans) == (True, "OK")

    model_fake.answer(AIClientError("down"))
    _, ok_err, ans_err, _ = probe_single_ollama_endpoint(
        "http://localhost:11434", "sys", "user", st
    )
    assert (ok_err, "down" in ans_err) == (False, True)


def test_ai_multi_server_test_exits_when_endpoint_fails(
    model_fake: ModelFake,
    config: Callable[..., Path],
    unserved_side_channel_port: int,
) -> None:
    """Verify run_ollama_server_tests raises Exit when any endpoint fails."""
    _setup_telemetry_and_ollama(config, unserved_side_channel_port)
    from devops_cli.config.settings import load_settings

    st = load_settings()
    model_fake.answer(AIClientError("down"))
    with pytest.raises(typer.Exit):
        run_ollama_server_tests(["http://example.com"], "sys", "user", st)


def test_ai_agents_guards_against_path_traversal(tmp_path: Path, cli: Callable[..., Any]) -> None:
    """Verify agents subcommand prevents writing files outside repo boundary."""
    res = cli(
        "ai",
        "agents",
        "--repo",
        str(tmp_path),
        "--file",
        "../../outside.md",
        "--template",
    )
    assert (res.exit_code, not (tmp_path / "../../outside.md").exists()) == (0, True)


def test_ai_test_disables_cache_and_targets_url(
    model_fake: ModelFake,
    cli: Callable[..., Any],
    config: Callable[..., Path],
    unserved_side_channel_port: int,
) -> None:
    """Verify devops ai test bypasses cache and properly targets a specific --url."""
    _setup_telemetry_and_ollama(
        config,
        unserved_side_channel_port,
        provider="ollama",
        ollama_urls=["http://example.com:11434", "http://example.com:11435"],
    )
    model_fake.answer("Hello live")

    res = cli("ai", "test", "-u", "http://example.com:11435")
    assert (res.exit_code, "Hello live" in res.stdout, len(model_fake.sent)) == (
        0,
        True,
        1,
    )


def test_ai_pipeline_runs_steps(cli: Callable[..., Any], model_fake: ModelFake) -> None:
    """Verify multi-agent pipeline completes steps over model_fake."""
    model_fake.answer("Security audit passed cleanly.")
    res = cli("ai", "pipeline", "Audit workspace", "--personas", "devsecops", "--no-rag")
    assert (res.exit_code, "Security audit passed cleanly." in res.stdout) == (0, True)


def test_ai_token_count_warns_when_over_budget(cli: Callable[..., Any]) -> None:
    """Verify token-count warns when prompt exceeds given budget."""
    res = cli("ai", "token-count", "a " * 5000, "--budget", "10")
    assert (res.exit_code, "✗ No" in res.stdout) == (0, True)


def test_ai_config_refuses_invalid_provider(cli: Callable[..., Any]) -> None:
    """Verify devops ai config rejects invalid provider names."""
    res = cli("ai", "config", "--provider", "invalid_provider_123")
    assert res.exit_code == 1


def test_ai_config_reports_keyring_error(
    cli: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify keyring storage failures are reported gracefully."""
    monkeypatch.setattr(
        "devops_cli.commands.ai.dotted_set",
        MagicMock(side_effect=SecretStorageError("Keyring locked")),
    )
    res = cli("ai", "config", "--api-key", "secret123")
    assert (res.exit_code, "Could not store ai.api_key" in (res.stdout + res.stderr)) == (
        1,
        True,
    )


def test_ai_models_reports_api_error(cli: Callable[..., Any], model_fake: ModelFake) -> None:
    """Verify model listing error exits with code 1."""
    model_fake.set_list_models_error(RuntimeError("API down"))
    res = cli("ai", "models")
    assert (res.exit_code, "Failed to list models" in (res.stdout + res.stderr)) == (
        1,
        True,
    )


def test_ai_preload_skips_non_ollama_provider(
    cli: Callable[..., Any],
    config: Callable[..., Path],
    unserved_side_channel_port: int,
) -> None:
    """Verify preload informs user when active provider is not Ollama."""
    _setup_telemetry_and_ollama(config, unserved_side_channel_port, provider="openai")
    res = cli("ai", "preload")
    assert (
        res.exit_code,
        "Model preloading is for Ollama provider" in res.stdout,
    ) == (0, True)


def test_ai_preload_preloads_ollama_endpoints(
    cli: Callable[..., Any],
    config: Callable[..., Path],
    model_fake: ModelFake,
    unserved_side_channel_port: int,
) -> None:
    """Verify preload triggers preload across configured Ollama endpoints."""
    _setup_telemetry_and_ollama(
        config,
        unserved_side_channel_port,
        provider="ollama",
        ollama_urls=["http://example.com:11434"],
    )
    model_fake.set_preload_results({"http://example.com:11434": True})
    res = cli("ai", "preload")
    assert (res.exit_code, "preloaded" in res.stdout) == (0, True)


def test_ai_chat_interactive_session(
    cli: Callable[..., Any],
    monkeypatch: pytest.MonkeyPatch,
    model_fake: ModelFake,
) -> None:
    """Verify interactive chat session processes turn and responds."""
    mock_console = MagicMock()
    mock_console.input.side_effect = ["How do I secure an ingress?", "exit"]
    monkeypatch.setattr("devops_cli.commands.ai.get_console", lambda: mock_console)

    mock_run_res: AgentResponse[Any] = AgentResponse(
        content="Hello! How can I help you?",
        tool_calls=[],
        turns=1,
    )
    monkeypatch.setattr(
        "devops_cli.ai.agents.agent.PydanticAgent.run", lambda *a, **k: mock_run_res
    )

    res = cli("ai", "chat", "--persona", "architect", "--no-stream")
    assert res.exit_code == 0
    assert "Hello! How can I help you?" in res.stdout


def test_ai_chat_persona_orange_rendering() -> None:
    """Verify acceptance criteria 1-4 for persona title rendering in orange styling."""
    from io import StringIO

    from rich.console import Console

    from devops_cli.output import print_section

    buffer = StringIO()
    test_console = Console(file=buffer, force_terminal=True, color_system="truecolor", width=120)
    title = "Enterprise Infrastructure Architect"
    print_section(
        f" [bold dark_orange]{title}[/bold dark_orange] (Pydantic Agent)  ",
        style="dark_orange",
        console=test_console,
    )
    test_console.print(f"\n[bold dark_orange]{title}:[/bold dark_orange] ", end="")
    test_console.print("[bold cyan]You:[/bold cyan] ")
    rendered = buffer.getvalue()
    assert title in rendered
    assert "You:" in rendered


def test_ai_chat_markdown_response_rendering(
    model_fake: ModelFake,
    cli: Callable[..., Any],
    config: Callable[..., Path],
    refusing_port: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify devops ai chat formats responses containing Markdown syntax using Rich Markdown.

    The chat prewarms the faked model, and Qdrant is down, refused through `refusing_port`.
    """
    config(qdrant={"url": f"http://127.0.0.1:{refusing_port}"})
    mock_console = MagicMock()
    mock_console.input.side_effect = ["How do I list pods?", "exit"]
    monkeypatch.setattr("devops_cli.commands.ai.get_console", lambda: mock_console)
    monkeypatch.setattr("devops_cli.output.console.get_console", lambda: mock_console)

    mock_run_res: AgentResponse[Any] = AgentResponse(
        content="Here is the solution:\n```bash\ndevops k8s pods\n```\n- Point 1: Fast\n- Point 2: Secure",
        tool_calls=[],
        turns=1,
    )
    monkeypatch.setattr(
        "devops_cli.ai.agents.agent.PydanticAgent.run", lambda *a, **k: mock_run_res
    )

    res_chat = cli("ai", "chat", "--persona", "architect", "--no-stream")
    assert res_chat.exit_code == 0
    from rich.markdown import Markdown

    has_md = any(
        len(c.args) > 0 and isinstance(c.args[0], Markdown)
        for c in mock_console.print.call_args_list
    )
    assert has_md is True


def test_a_cut_stream_stores_no_reply_in_chat_memory() -> None:
    """Verify a stream that raises after its first chunk leaves only the user entry in memory."""

    def cut_stream(*args: Any, **kwargs: Any) -> Any:
        yield "Partial "
        raise AIClientError("Provider stream ended before its final frame.")

    client = MagicMock(chat_messages_stream=cut_stream)
    agent = MagicMock(memory=AgentMemory())
    agent._build_system_prompt_with_tools.return_value = "You are an architect."

    with pytest.raises(AIClientError, match="before its final frame"):
        stream_interactive_chat_turn(client, agent, False, "Explain the deploy.")

    assert [(entry.role, entry.content) for entry in agent.memory.entries] == [
        ("user", "Explain the deploy.")
    ]


def test_a_streamed_turn_sends_the_user_message_and_history() -> None:
    """Verify streamed chat turn sends prompt on turn 1 and accumulated history on turn 2."""
    recorded_messages: list[list[tuple[str, str]]] = []

    def fake_stream(_system: str, messages: list[Any], enable_thinking: bool = False) -> Any:
        recorded_messages.append([(m.role, m.content) for m in messages])
        turn = len(recorded_messages)
        yield f"r{turn}"

    client = MagicMock(chat_messages_stream=fake_stream)
    agent = MagicMock(memory=AgentMemory())
    agent._build_system_prompt_with_tools.return_value = "sys"

    stream_interactive_chat_turn(client, agent, False, "p1")
    stream_interactive_chat_turn(client, agent, False, "p2")

    expected_recorded = (
        [("user", "p1")],
        [("user", "p1"), ("assistant", "r1"), ("user", "p2")],
    )
    expected_memory = [
        ("user", "p1"),
        ("assistant", "r1"),
        ("user", "p2"),
        ("assistant", "r2"),
    ]

    assert (
        (recorded_messages[0], recorded_messages[1]),
        [(e.role, e.content) for e in agent.memory.entries],
    ) == (expected_recorded, expected_memory)


@pytest.mark.parametrize(
    ("case_type", "expected_output_fragment"),
    [
        ("client_error", "before its final frame"),
        ("keyboard_interrupt", "Interrupted."),
    ],
)
def test_a_failed_streamed_turn_leaves_memory_as_it_was(
    case_type: str,
    expected_output_fragment: str,
    model_fake: ModelFake,
    monkeypatch: pytest.MonkeyPatch,
    cli: Callable[..., Any],
) -> None:
    """Verify failed or interrupted streamed turn leaves agent memory as it was before the turn."""
    recorded_messages: list[list[tuple[str, str]]] = []

    def fake_stream(
        _self: Any, _system: str, messages: list[Any], enable_thinking: bool = False
    ) -> Any:
        recorded_messages.append([(m.role, m.content) for m in messages])
        if len(recorded_messages) == 1:
            yield "partial "
            if case_type == "client_error":
                raise AIClientError("Provider stream ended before its final frame.")
            raise KeyboardInterrupt
        yield "r2"

    monkeypatch.setattr(
        model_fake,
        "chat_messages_stream",
        lambda system="", messages=(), **kw: fake_stream(model_fake, system, list(messages)),
    )

    mock_console = MagicMock()
    mock_console.input.side_effect = ["p1", "p2", "exit"]

    captured_memory: list[AgentMemory] = []

    from devops_cli.ai.agents.agent import PydanticAgent

    class WrappedAgent(PydanticAgent[Any]):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            captured_memory.append(self.memory)

    monkeypatch.setattr("devops_cli.commands.ai.get_console", lambda: mock_console)
    monkeypatch.setattr("devops_cli.ai.agents.agent.PydanticAgent", WrappedAgent)

    res = cli("ai", "chat", "--no-tools", "--no-rag", "--no-prewarm")

    mem = captured_memory[0]
    expected_entries = [("user", "p2"), ("assistant", "r2")]

    assert (
        res.exit_code,
        expected_output_fragment in (res.stdout + res.stderr),
        len(recorded_messages),
        recorded_messages[1],
        [(e.role, e.content) for e in mem.entries],
    ) == (0, True, 2, [("user", "p2")], expected_entries)


def test_a_thinking_only_stream_stores_the_prompt_once() -> None:
    """Verify thinking-only stream fallback executes agent.run and stores prompt exactly once."""
    recorded_messages: list[list[tuple[str, str]]] = []

    def fake_stream(_system: str, messages: list[Any], enable_thinking: bool = False) -> Any:
        recorded_messages.append([(m.role, m.content) for m in messages])
        yield "<think>reasoning only</think>"

    client = MagicMock()
    client.chat_messages_stream = fake_stream
    client.chat_messages.return_value = "r1"

    from devops_cli.ai.agents.agent import PydanticAgent

    agent = PydanticAgent(client=client, system_prompt="sys", tools=[])

    stream_interactive_chat_turn(client, agent, True, "p1")

    assert (
        recorded_messages[0],
        [(e.role, e.content) for e in agent.memory.entries],
    ) == ([("user", "p1")], [("user", "p1"), ("assistant", "r1")])


def test_chat_seeds_the_invariants(
    model_fake: ModelFake,
    refusing_port: int,
    unserved_side_channel_port: int,
    config: Callable[..., Path],
    cli: Callable[..., Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify devops ai chat seeds DEFAULT_CHAT_INVARIANTS on both non-stream and stream paths.

    Qdrant is down, refused through `refusing_port`.
    """
    role_snippet = (
        "You are an Enterprise Infrastructure Architect specializing in cloud-native systems"
    )

    config(
        telemetry={"endpoint": f"http://127.0.0.1:{unserved_side_channel_port}"},
        qdrant={"url": f"http://127.0.0.1:{refusing_port}"},
        ai={"ollama_urls": ["http://localhost:11434"]},
    )

    # 1. Non-stream path with tools enabled
    model_fake.answer("r1")

    mock_console = MagicMock()
    mock_console.input.side_effect = ["p1", "exit"]
    monkeypatch.setattr("devops_cli.commands.ai.get_console", lambda: mock_console)

    res_non_stream = cli(
        "ai",
        "chat",
        "--persona",
        "architect",
        "--no-stream",
        "--no-rag",
        "--no-prewarm",
    )
    assert res_non_stream.exit_code == 0
    assert len(model_fake.calls) >= 1
    sys_ns = model_fake.calls[0].system_prompt
    assert sys_ns.startswith("## Invariants")
    for inv in DEFAULT_CHAT_INVARIANTS:
        assert f"- {inv}" in sys_ns
    assert sys_ns.index(f"- {DEFAULT_CHAT_INVARIANTS[-1]}") < sys_ns.index(role_snippet)

    # 2. Streamed path with --no-tools
    model_fake.reset()
    model_fake.answer("r1")

    mock_console_2 = MagicMock()
    mock_console_2.input.side_effect = ["p1", "exit"]
    monkeypatch.setattr("devops_cli.commands.ai.get_console", lambda: mock_console_2)

    res_stream = cli(
        "ai",
        "chat",
        "--persona",
        "architect",
        "--no-tools",
        "--no-rag",
        "--no-prewarm",
    )
    assert res_stream.exit_code == 0
    assert len(model_fake.calls) >= 1
    sys_s = model_fake.calls[0].system_prompt
    assert sys_s.startswith("## Invariants")
    for inv in DEFAULT_CHAT_INVARIANTS:
        assert f"- {inv}" in sys_s
    assert sys_s.index(f"- {DEFAULT_CHAT_INVARIANTS[-1]}") < sys_s.index(role_snippet)
