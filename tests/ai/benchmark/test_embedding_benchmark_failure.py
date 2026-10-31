"""Tests verifying embedding benchmark defaults and failure behavior (#1165)."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from typer.testing import CliRunner

from devops_cli.ai.benchmark.embedding_runner import EmbeddingBenchmarkReport
from devops_cli.main import app

runner = CliRunner()


def test_embedding_benchmark_defaults_to_gateway_embedding_model(
    isolate_devops_cli_config: Any,
) -> None:
    """Embedding benchmark defaults to devops-embedding when gateway provider is configured."""
    isolate_devops_cli_config.write_text(
        "ai:\n  provider: gateway\n  gateway_url: https://gateway.example.com/v1\n",
        encoding="utf-8",
    )
    with patch("devops_cli.commands.benchmark._execute_embedding_benchmark") as mock_exec:
        result = runner.invoke(app, ["ai", "benchmark", "--type", "embedding"])
        assert result.exit_code == 0
        assert mock_exec.called
        model_list = mock_exec.call_args[1].get("model_list") or mock_exec.call_args[0][0]
        assert model_list == ["devops-embedding"]


def test_embedding_benchmark_all_failed_exits_nonzero_and_does_not_save_run(
    isolate_devops_cli_config: Any,
) -> None:
    """When every request in embedding benchmark fails, exit non-zero and do not save run."""
    isolate_devops_cli_config.write_text(
        "ai:\n  provider: gateway\n  gateway_url: https://gateway.example.com/v1\n",
        encoding="utf-8",
    )
    failed_report = EmbeddingBenchmarkReport(
        session_id="test-session",
        provider="gateway",
        results=[],
        failed_count=5,
        total_count=5,
    )
    with (
        patch(
            "devops_cli.ai.benchmark.embedding_runner.EmbeddingBenchmarkRunner.run",
            return_value=failed_report,
        ),
        patch("devops_cli.commands.benchmark._record_benchmark") as mock_record,
    ):
        result = runner.invoke(app, ["ai", "benchmark", "--type", "embedding"])
        assert result.exit_code != 0
        assert not mock_record.called
