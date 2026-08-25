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

        res_test = runner.invoke(ai_app, ["test", "--prompt", "Ping"])
        assert res_test.exit_code == 0

        res_models = runner.invoke(ai_app, ["models"])
        assert res_models.exit_code == 0

        res_agents = runner.invoke(ai_app, ["agents", "--template", "--repo", str(tmp_path)])
        assert res_agents.exit_code == 0
