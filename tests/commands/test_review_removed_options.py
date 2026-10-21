"""Verify that removed persona and reranking CLI options exit 2 as unknown options (#1151)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.review import app

runner = CliRunner()


@pytest.mark.parametrize(
    "subcommand,args",
    [
        ("path", [".", "--persona", "devsecops"]),
        ("path", [".", "--all"]),
        ("path", [".", "--no-persona-review"]),
        ("path", [".", "--persona-review-only"]),
        ("path", [".", "--no-reranking"]),
        ("path", [".", "--reranking-only"]),
        ("branch", ["main", "--persona", "devsecops"]),
        ("branch", ["main", "--all"]),
        ("branch", ["main", "--no-persona-review"]),
        ("branch", ["main", "--no-reranking"]),
        ("pr", ["1", "--persona", "devsecops"]),
        ("pr", ["1", "--all"]),
        ("pr", ["1", "--no-persona-review"]),
        ("pr", ["1", "--no-reranking"]),
        ("benchmark", [".", "--persona", "devsecops"]),
        ("benchmark", [".", "--all"]),
        ("samples", ["validate", "--all"]),
    ],
)
def test_removed_review_options_exit_2(subcommand: str, args: list[str]) -> None:
    """Removed options must exit 2 with an unknown option error message."""
    cmd_args = [subcommand, *args] if subcommand != "samples" else ["samples", *args]
    with (
        patch("devops_cli.commands.review._execute_review_workflow", return_value=[]),
        patch(
            "devops_cli.commands.review._prepare_pr_content",
            return_value=([], "", [], None, None, "base", "head"),
        ),
        patch(
            "devops_cli.commands.review._prepare_branch_content",
            return_value=([], "", [], None, None),
        ),
        patch("devops_cli.commands.review._prepare_path_content", return_value=([], "", [])),
        patch("devops_cli.commands.review._select_samples", return_value=[]),
    ):
        result = runner.invoke(app, cmd_args)
    assert result.exit_code == 2
    assert (
        "no such option" in result.output.lower()
        or "unexpected option" in result.output.lower()
        or "error" in result.output.lower()
    )
