"""Tests for metadata task model configuration used by analyze and ai agents (#1068)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.ai.client import LLMClient
from devops_cli.config.settings import AIConfig, reset_settings_cache
from devops_cli.main import app
from devops_cli.models.git import ChangedFile
from tests.support.fakes.github import (
    pull_request_file_payload,
    pull_request_payload,
    route_pull_request,
)

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake

pytestmark = pytest.mark.usefixtures("keyring_store")
runner = CliRunner(env={"COLUMNS": "200", "NO_COLOR": "1", "TERM": "dumb"})


@pytest.fixture(autouse=True)
def _isolate_settings() -> Iterator[None]:
    reset_settings_cache()
    yield
    reset_settings_cache()


@pytest.mark.live("find")
def test_metadata_task_model_override_used_by_analyze_and_agents(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify analyze --enhanced and ai agents use the metadata task model override."""
    monkeypatch.setenv("DEVOPS_CLI_AI_TASK_METADATA_MODEL", "devops-background")
    reset_settings_cache()

    (tmp_path / ".git").mkdir()
    (tmp_path / "sample.py").write_text(
        "def hello() -> str:\n    return 'world'\n", encoding="utf-8"
    )

    recorded_configs: list[AIConfig] = []
    orig_init = LLMClient.__init__

    def recording_init(self: LLMClient, *args: Any, **kwargs: Any) -> None:
        cfg = kwargs.get("config") or (args[0] if args else None)
        if cfg is not None and isinstance(cfg, AIConfig):
            recorded_configs.append(cfg)
        orig_init(self, *args, **kwargs)

    monkeypatch.setattr(LLMClient, "__init__", recording_init)
    monkeypatch.setattr(
        LLMClient, "chat", lambda *a, **kw: "# AGENTS.md\nArchitecture and standards."
    )
    monkeypatch.setattr(LLMClient, "chat_messages", lambda *a, **kw: None)
    monkeypatch.setattr("devops_cli.commands.ai._try_retrieve_rag_context", lambda *a, **kw: None)

    # 1. devops analyze path --enhanced
    with patch("devops_cli.commands.analyze.find_repo_root", return_value=tmp_path):
        res_analyze = runner.invoke(app, ["ai", "analyze", "path", str(tmp_path), "--enhanced"])
        assert res_analyze.exit_code == 0, res_analyze.output

    assert len(recorded_configs) == 1
    assert recorded_configs[0].model == "devops-background"

    # 2. devops ai agents
    res_agents = runner.invoke(app, ["ai", "agents", "--repo", str(tmp_path), "--force"])
    assert res_agents.exit_code == 0, res_agents.output

    assert len(recorded_configs) == 2
    assert recorded_configs[1].model == "devops-background"


@pytest.mark.live("find")
def test_metadata_task_model_fallback_to_global_when_unset(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify analyze --enhanced and ai agents fall back to global ai settings when unset."""
    monkeypatch.delenv("DEVOPS_CLI_AI_TASK_METADATA_MODEL", raising=False)
    monkeypatch.delenv("DEVOPS_CLI_AI_TASK_METADATA_PROVIDER", raising=False)
    reset_settings_cache()

    (tmp_path / ".git").mkdir()
    (tmp_path / "sample.py").write_text(
        "def hello() -> str:\n    return 'world'\n", encoding="utf-8"
    )

    recorded_configs: list[AIConfig] = []
    orig_init = LLMClient.__init__

    def recording_init(self: LLMClient, *args: Any, **kwargs: Any) -> None:
        cfg = kwargs.get("config") or (args[0] if args else None)
        if cfg is not None and isinstance(cfg, AIConfig):
            recorded_configs.append(cfg)
        orig_init(self, *args, **kwargs)

    monkeypatch.setattr(LLMClient, "__init__", recording_init)
    monkeypatch.setattr(
        LLMClient, "chat", lambda *a, **kw: "# AGENTS.md\nArchitecture and standards."
    )
    monkeypatch.setattr(LLMClient, "chat_messages", lambda *a, **kw: None)
    monkeypatch.setattr("devops_cli.commands.ai._try_retrieve_rag_context", lambda *a, **kw: None)

    with patch("devops_cli.commands.analyze.find_repo_root", return_value=tmp_path):
        res_analyze = runner.invoke(app, ["ai", "analyze", "path", str(tmp_path), "--enhanced"])
        assert res_analyze.exit_code == 0, res_analyze.output

    assert len(recorded_configs) == 1
    global_model = recorded_configs[0].model
    # Unset metadata task model must NOT be devops-background
    assert global_model != "devops-background"

    res_agents = runner.invoke(app, ["ai", "agents", "--repo", str(tmp_path), "--force"])
    assert res_agents.exit_code == 0, res_agents.output

    assert len(recorded_configs) == 2
    assert recorded_configs[1].model == global_model


def test_metadata_task_model_override_used_by_analyze_branch_and_pr(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    github_api: GitHubApiFake,
) -> None:
    """Verify analyze branch --enhanced and pr --enhanced use the metadata task model override."""
    monkeypatch.setenv("DEVOPS_CLI_AI_TASK_METADATA_MODEL", "devops-background")
    reset_settings_cache()

    (tmp_path / ".git").mkdir()
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    worker_file = src_dir / "worker.py"
    worker_file.write_text("def do_work(): pass\n", encoding="utf-8")
    route_pull_request(
        github_api,
        "org/repo",
        42,
        pull_request_payload(title="Add worker"),
        files=[pull_request_file_payload("src/worker.py")],
    )

    recorded_configs: list[AIConfig] = []
    orig_init = LLMClient.__init__

    def recording_init(self: LLMClient, *args: Any, **kwargs: Any) -> None:
        cfg = kwargs.get("config") or (args[0] if args else None)
        if cfg is not None and isinstance(cfg, AIConfig):
            recorded_configs.append(cfg)
        orig_init(self, *args, **kwargs)

    monkeypatch.setattr(LLMClient, "__init__", recording_init)
    monkeypatch.setattr(LLMClient, "chat_messages", lambda *a, **kw: None)

    with (
        patch("devops_cli.commands.analyze.find_repo_root", return_value=tmp_path),
        patch(
            "devops_cli.git.operations.list_branches", return_value=MagicMock(current="feat/worker")
        ),
        patch(
            "devops_cli.git.operations.list_changed_files",
            return_value=[ChangedFile(change_type="modified", path="src/worker.py")],
        ),
        patch("devops_cli.git.operations.resolve_merge_base", return_value="base-sha"),
        patch("devops_cli.git.operations.read_file_at_revision", return_value=None),
        patch("devops_cli.core.repo.get_repo_origin_name", return_value="org/repo"),
    ):
        res_branch = runner.invoke(app, ["ai", "analyze", "branch", "feat/worker", "--enhanced"])
        assert res_branch.exit_code == 0, res_branch.output
        assert len(recorded_configs) == 1
        assert recorded_configs[0].model == "devops-background"

        res_pr = runner.invoke(app, ["ai", "analyze", "pr", "42", "--enhanced"])
        assert res_pr.exit_code == 0, res_pr.output
        assert len(recorded_configs) == 2
        assert recorded_configs[1].model == "devops-background"
