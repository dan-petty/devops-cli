"""Unit tests for the devops ai CLI subcommands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.ai.client import LLMClient
from devops_cli.commands.ai import app as ai_app
from devops_cli.config.settings import Settings

runner = CliRunner()


def test_ai_subcommands_execution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify execution of devops ai config, test, models, and agents subcommands."""
    monkeypatch.setattr(
        "devops_cli.core.validation.validate_service_url", lambda *args, **kwargs: None
    )
    mock_resp = MagicMock()
    mock_resp.__str__.return_value = "OK"
    mock_resp.wall_seconds = 0.5
    mock_resp.backend_info = "mock"

    with (
        patch.object(LLMClient, "chat", return_value=mock_resp),
        patch.object(LLMClient, "list_models", return_value=["gemma4:26b"]),
        patch("devops_cli.config.settings.load_settings", return_value=Settings()),
    ):
        res_config = runner.invoke(ai_app, ["config"])
        assert res_config.exit_code == 0

        res_config_set = runner.invoke(
            ai_app, ["config", "--provider", "ollama", "--model", "qwen2.5-coder"]
        )
        assert res_config_set.exit_code == 0

        res_test = runner.invoke(ai_app, ["test", "--prompt", "Ping"])
        assert res_test.exit_code == 0

        res_models = runner.invoke(ai_app, ["models"])
        assert res_models.exit_code == 0

        res_agents = runner.invoke(ai_app, ["agents", "--template", "--repo", str(tmp_path)])
        assert res_agents.exit_code == 0

        res_agents_file = runner.invoke(
            ai_app, ["agents", "--template", "--file", "AGENTS.md", "--repo", str(tmp_path)]
        )
        assert res_agents_file.exit_code == 0


def test_ai_chat_and_agent(tmp_path: Path) -> None:
    """Test ai chat execution and explain."""
    mock_resp = MagicMock()
    mock_resp.__str__.return_value = "Agent response"
    mock_resp.wall_seconds = 0.3
    mock_resp.backend_info = "mock"
    mock_resp.tool_calls = []

    with (
        patch.object(LLMClient, "chat", return_value=mock_resp),
        patch("devops_cli.config.settings.load_settings", return_value=Settings()),
    ):
        res_chat_explain = runner.invoke(ai_app, ["chat", "--explain"])
        assert res_chat_explain.exit_code == 0

        res_preload = runner.invoke(ai_app, ["preload"])
        assert res_preload.exit_code == 0


def test_ai_token_count_and_route(tmp_path: Path) -> None:
    """Test ai token-count and route subcommands."""
    sample_file = tmp_path / "code.py"
    sample_file.write_text("def foo():\n    return 42\n", encoding="utf-8")

    res_tc_text = runner.invoke(ai_app, ["token-count", "Hello world from devops CLI"])
    assert res_tc_text.exit_code == 0
    assert "Token Budget Report" in res_tc_text.output or "AI Context" in res_tc_text.output

    res_tc_json = runner.invoke(ai_app, ["token-count", str(sample_file), "--json"])
    assert res_tc_json.exit_code == 0
    assert "estimated_tokens" in res_tc_json.output

    res_route = runner.invoke(ai_app, ["route", "multi-file architecture review"])
    assert res_route.exit_code == 0

    res_route_json = runner.invoke(
        ai_app, ["route", "token budgeting", "--tokens", "500", "--json"]
    )
    assert res_route_json.exit_code == 0
    assert "complexity" in res_route_json.output


def test_ai_bundle_models_and_pipeline(tmp_path: Path) -> None:
    """Test ai bundle-models and pipeline subcommands."""
    with patch(
        "devops_cli.ai.bundle.bundle_ollama_models", return_value=(2, tmp_path / "models.tar.gz")
    ):
        res_bundle = runner.invoke(ai_app, ["bundle-models", "--output", str(tmp_path)])
        assert res_bundle.exit_code == 0

    mock_result = MagicMock()
    mock_result.steps = []
    mock_result.total_turns = 0
    mock_result.all_tool_calls = []

    with (
        patch("devops_cli.ai.agents.pipeline.MultiAgentPipeline.run", return_value=mock_result),
        patch("devops_cli.config.settings.load_settings", return_value=Settings()),
    ):
        res_pipe = runner.invoke(ai_app, ["pipeline", "Review system", "--max-turns", "2"])
        assert res_pipe.exit_code == 0


def test_ai_explain() -> None:
    """Test ai --explain flag."""
    with patch("devops_cli.ai.explain.render_explanation"):
        res = runner.invoke(ai_app, ["--explain"])
        assert res.exit_code == 0


def test_ai_collect_project_context_and_agents_llm(tmp_path: Path) -> None:
    """Verify _collect_project_context and agents command with LLM generation."""
    from devops_cli.ai.client import LLMResponse
    from devops_cli.commands.ai import _collect_project_context

    # Create dummy project files
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Demo Project\n", encoding="utf-8")
    (tmp_path / ".editorconfig").write_text("root = true\n", encoding="utf-8")
    (tmp_path / ".devcontainer").mkdir()
    (tmp_path / ".devcontainer" / "devcontainer.json").write_text(
        '{"name": "demo"}', encoding="utf-8"
    )

    ctx = _collect_project_context(tmp_path)
    assert "pyproject.toml" in ctx
    assert "README.md" in ctx
    assert ".editorconfig" in ctx
    assert "devcontainer.json" in ctx

    # Test agents command with LLM response
    mock_resp = LLMResponse(
        content="# AGENTS.md content\nArchitecture and standards.", wall_seconds=0.5
    )
    with (
        patch("devops_cli.ai.client.LLMClient.chat", return_value=mock_resp),
        patch("devops_cli.config.settings.load_settings", return_value=Settings()),
    ):
        res_agents = runner.invoke(
            ai_app, ["agents", "--repo", str(tmp_path), "--file", "AGENTS.md"]
        )
        assert res_agents.exit_code == 0
        assert (tmp_path / "AGENTS.md").exists()


def test_ai_error_branches_and_chat_helpers(tmp_path: Path) -> None:
    """Verify test multi-node failure, preload non-ollama, and print helpers."""
    from devops_cli.commands.ai import _print_chat_thought, _print_chat_tool

    # Print helpers
    _print_chat_thought("Checking dependencies")
    _print_chat_tool("search", {"query": "test"}, "Found 3 results")

    # Unknown persona in chat
    res_bad_persona = runner.invoke(ai_app, ["chat", "--persona", "nonexistent_persona"])
    assert res_bad_persona.exit_code == 1

    # Unknown persona in pipeline
    res_bad_pipe = runner.invoke(ai_app, ["pipeline", "--personas", "bad_persona"])
    assert res_bad_pipe.exit_code == 1

    # Pipeline dry run
    from devops_cli.dry_run import set_dry_run

    set_dry_run(True)
    try:
        res_pipe_dry = runner.invoke(ai_app, ["pipeline", "review repo"])
        assert res_pipe_dry.exit_code == 0
    finally:
        set_dry_run(False)

    # Config options update
    res_cfg_up = runner.invoke(
        ai_app,
        [
            "config",
            "--ollama-max-parallel",
            "4",
            "--api-base-url",
            "https://api.openai.com/v1",
            "--max-retries",
            "3",
        ],
    )
    assert res_cfg_up.exit_code == 0


def test_ai_multi_server_test_and_agents_validation(tmp_path: Path) -> None:
    """Verify parallel ollama server tests, failed chat handling, and agent path traversal guards."""
    from devops_cli.ai.client import AIClientError
    from devops_cli.commands.ai import _run_ollama_server_tests, _test_single_ollama_endpoint

    # 1. _test_single_ollama_endpoint
    st = Settings()
    st.ai.ollama_urls = ["http://localhost:11434"]
    with patch("devops_cli.ai.client.LLMClient.chat", return_value="OK"):
        u, ok, ans, wall = _test_single_ollama_endpoint("http://localhost:11434", "sys", "user", st)
        assert ok is True
        assert ans == "OK"

    with patch("devops_cli.ai.client.LLMClient.chat", side_effect=AIClientError("down")):
        u, ok, ans, wall = _test_single_ollama_endpoint("http://localhost:11434", "sys", "user", st)
        assert ok is False
        assert "down" in ans

    # 2. _run_ollama_server_tests failure raises Exit
    with (
        patch(
            "devops_cli.commands.ai._test_single_ollama_endpoint",
            return_value=("http://node1", False, "error", "0s"),
        ),
        pytest.raises(Exception),
    ):
        _run_ollama_server_tests(["http://node1"], "sys", "user", st)

    # 3. agents path outside repo
    res_outside = runner.invoke(
        ai_app,
        ["agents", "--repo", str(tmp_path), "--file", "../../outside.md", "--template"],
    )
    assert res_outside.exit_code == 0
    assert not (tmp_path / "../../outside.md").exists()


def test_ai_extended_commands(tmp_path: Path) -> None:
    """Verify bundle-models, token-count, route, and live pipeline commands."""
    from devops_cli.ai.agents.pipeline import MultiAgentPipelineResult, PipelineStepResult

    # 1. bundle-models
    with patch(
        "devops_cli.ai.bundle.bundle_ollama_models", return_value=(2, tmp_path / "models.tar.gz")
    ):
        res_bundle = runner.invoke(ai_app, ["bundle-models", "--output", str(tmp_path)])
        assert res_bundle.exit_code == 0
        assert "Bundled 2 model(s)" in res_bundle.output

    # 2. token-count for text and file
    sample_f = tmp_path / "code.py"
    sample_f.write_text("print('hello world')", encoding="utf-8")

    res_tc_text = runner.invoke(ai_app, ["token-count", "def test(): pass"])
    assert res_tc_text.exit_code == 0
    assert "Token Budget" in res_tc_text.output or "tokens" in res_tc_text.output.lower()

    res_tc_file = runner.invoke(ai_app, ["token-count", str(sample_f), "--json"])
    assert res_tc_file.exit_code == 0
    assert "estimated_tokens" in res_tc_file.output

    # 3. route command
    res_route = runner.invoke(ai_app, ["route", "Review this Python code"])
    assert res_route.exit_code == 0
    assert "Task Name" in res_route.output or "AI Task Dynamic Routing" in res_route.output

    # 4. pipeline live execution with mock
    mock_res = MultiAgentPipelineResult(
        final_content="Security audit passed cleanly.",
        steps=[
            PipelineStepResult(
                agent_name="Principal DevSecOps Engineer",
                content="Security audit passed cleanly.",
            )
        ],
        total_turns=1,
    )
    with patch("devops_cli.ai.agents.pipeline.MultiAgentPipeline.run", return_value=mock_res):
        res_pipe = runner.invoke(
            ai_app,
            ["pipeline", "Audit workspace", "--personas", "devsecops", "--no-rag"],
        )
        assert res_pipe.exit_code == 0
        assert "Security audit passed cleanly." in res_pipe.output

    # 5. route with --json and --frontier
    res_route_json = runner.invoke(
        ai_app, ["route", "Deploy cluster", "--frontier", "--tokens", "50000", "--json"]
    )
    assert res_route_json.exit_code == 0
    assert "task_name" in res_route_json.output

    # 6. pipeline unknown persona
    res_unknown_p = runner.invoke(ai_app, ["pipeline", "Goal", "--personas", "invalid_persona_xyz"])
    assert res_unknown_p.exit_code == 1

    # 7. token-count exceeding budget
    res_overflow = runner.invoke(ai_app, ["token-count", "a " * 5000, "--budget", "10"])
    assert res_overflow.exit_code == 0
    assert "✗ No" in res_overflow.output


def test_ai_config_models_preload_and_chat_interactive(tmp_path: Path) -> None:
    """Verify ai config, models, preload, chat interactive mode, and explain."""
    from devops_cli.ai.agents.pydantic_agent import AgentResponse
    from devops_cli.commands.ai import _print_chat_thought, _print_chat_tool
    from devops_cli.config.settings import SecretStorageError

    # 1. ai_main --explain
    with patch("devops_cli.ai.explain.render_explanation") as mock_exp:
        res_exp = runner.invoke(ai_app, ["--explain"])
        assert res_exp.exit_code == 0
        mock_exp.assert_called_once_with("benchmark")

    # 2. config without args shows table
    res_cfg_show = runner.invoke(ai_app, ["config"])
    assert res_cfg_show.exit_code == 0
    assert "AI Configuration" in res_cfg_show.output

    # 3. config with invalid provider
    res_bad_prov = runner.invoke(ai_app, ["config", "--provider", "invalid_provider_123"])
    assert res_bad_prov.exit_code == 1

    # 4. config with SecretStorageError
    with patch(
        "devops_cli.commands.ai.dotted_set", side_effect=SecretStorageError("Keyring locked")
    ):
        res_sec_err = runner.invoke(ai_app, ["config", "--api-key", "secret123"])
        assert res_sec_err.exit_code == 1
        assert "Could not store ai.api_key" in res_sec_err.output

    # 5. models command failure
    with patch("devops_cli.ai.client.LLMClient.list_models", side_effect=RuntimeError("API down")):
        res_mod_fail = runner.invoke(ai_app, ["models"])
        assert res_mod_fail.exit_code == 1
        assert "Failed to list models" in res_mod_fail.output

    # 6. models command success
    with patch("devops_cli.ai.client.LLMClient.list_models", return_value=["model-v1", "model-v2"]):
        res_mod_ok = runner.invoke(ai_app, ["models"])
        assert res_mod_ok.exit_code == 0
        assert "model-v1" in res_mod_ok.output

    # 7. preload with non-ollama provider
    st_openai = Settings()
    st_openai.ai.provider = "openai"
    with patch("devops_cli.config.settings.load_settings", return_value=st_openai):
        res_pre_non_ollama = runner.invoke(ai_app, ["preload"])
        assert res_pre_non_ollama.exit_code == 0
        assert "Model preloading is for Ollama provider" in res_pre_non_ollama.output

    # 8. preload with ollama provider
    st_ollama = Settings()
    st_ollama.ai.provider = "ollama"
    st_ollama.ai.ollama_urls = ["http://node1:11434"]
    with (
        patch("devops_cli.config.settings.load_settings", return_value=st_ollama),
        patch(
            "devops_cli.ai.client.LLMClient.preload_models",
            return_value={"http://node1:11434": True},
        ),
    ):
        res_pre_ok = runner.invoke(ai_app, ["preload"])
        assert res_pre_ok.exit_code == 0
        assert "preloaded" in res_pre_ok.output

    # 9. _print_chat_thought and _print_chat_tool helpers
    _print_chat_thought("Checking architectural boundaries...")
    _print_chat_tool("search_docs", {"query": "security", "top_k": 3}, "found 3 documents")

    # 10. chat command explain
    with patch("devops_cli.ai.explain.render_explanation") as mock_exp_chat:
        res_chat_exp = runner.invoke(ai_app, ["chat", "--explain"])
        assert res_chat_exp.exit_code == 0
        mock_exp_chat.assert_called_once_with("rag")

    # 11. chat command interactive session with exit input
    mock_run_res = AgentResponse(
        content="Hello! How can I help you?",
        tool_calls=[],
        turns=1,
    )
    with (
        patch("devops_cli.ai.agents.PydanticAgent.run", return_value=mock_run_res),
        patch(
            "devops_cli.commands.ai._try_retrieve_rag_context", return_value="RAG context snippet"
        ),
        patch("devops_cli.commands.ai.get_console") as mock_get_console,
    ):
        mock_console = MagicMock()
        mock_console.input.side_effect = ["How do I secure an ingress?", "exit"]
        mock_get_console.return_value = mock_console

        res_chat = runner.invoke(ai_app, ["chat", "--persona", "architect", "--no-stream"])
        assert res_chat.exit_code == 0
        assert "Hello! How can I help you?" in res_chat.output


def test_ai_token_count_route_pipeline_bundle(tmp_path: Path) -> None:
    """Verify ai token-count, route, pipeline, and bundle-models commands."""
    from unittest.mock import MagicMock, patch

    # 1. token-count text snippet
    res_tok_txt = runner.invoke(ai_app, ["token-count", "Sample query text for token budgeting"])
    assert res_tok_txt.exit_code == 0
    assert "AI Context Token Budget Report" in res_tok_txt.output

    # 2. token-count json output
    res_tok_json = runner.invoke(ai_app, ["token-count", "Text snippet", "--json"])
    assert res_tok_json.exit_code == 0
    assert "estimated_tokens" in res_tok_json.output

    # 3. token-count file target
    test_file = tmp_path / "sample.py"
    test_file.write_text("import sys\nprint('hello world')\n", encoding="utf-8")
    res_tok_file = runner.invoke(ai_app, ["token-count", str(test_file)])
    assert res_tok_file.exit_code == 0
    assert "sample.py" in res_tok_file.output

    # 4. route command table & json
    res_route_tbl = runner.invoke(ai_app, ["route", "complex_code_audit"])
    assert res_route_tbl.exit_code == 0
    assert "AI Task Dynamic Routing Decision" in res_route_tbl.output

    res_route_json = runner.invoke(ai_app, ["route", "fast_summary", "--json", "--frontier"])
    assert res_route_json.exit_code == 0
    assert "provider_name" in res_route_json.output

    # 5. pipeline command invalid persona
    res_pipe_bad = runner.invoke(ai_app, ["pipeline", "--personas", "invalid_persona_xyz"])
    assert res_pipe_bad.exit_code == 1

    # 6. pipeline command dry-run
    with patch("devops_cli.dry_run.is_dry_run", return_value=True):
        res_pipe_dry = runner.invoke(
            ai_app, ["pipeline", "Audit architecture", "--personas", "architect,qa"]
        )
        assert res_pipe_dry.exit_code == 0

    # 7. pipeline command execution
    mock_stage_step = MagicMock()
    mock_stage_step.agent_name = "Architect"
    mock_stage_step.content = "Architecture review completed: modular design verified."
    mock_stage_step.tool_calls = [MagicMock(tool_name="search_docs", arguments="{'query': 'k8s'}")]

    mock_pipeline_res = MagicMock()
    mock_pipeline_res.steps = [mock_stage_step]
    mock_pipeline_res.total_turns = 1
    mock_pipeline_res.all_tool_calls = mock_stage_step.tool_calls

    with (
        patch(
            "devops_cli.ai.agents.pipeline.MultiAgentPipeline.run", return_value=mock_pipeline_res
        ),
        patch(
            "devops_cli.commands.ai._try_retrieve_rag_context",
            return_value="Relevant RAG Architecture",
        ),
    ):
        res_pipe_ok = runner.invoke(ai_app, ["pipeline", "Review system boundaries"])
        assert res_pipe_ok.exit_code == 0
        assert "Multi-agent pipeline completed" in res_pipe_ok.output

    # 8. bundle-models command
    with patch(
        "devops_cli.ai.bundle.bundle_ollama_models",
        return_value=(2, Path("/tmp/ollama_bundle.tar.gz")),
    ):
        res_bundle = runner.invoke(ai_app, ["bundle-models"])
        assert res_bundle.exit_code == 0
        assert "Bundled 2 model(s)" in res_bundle.output
