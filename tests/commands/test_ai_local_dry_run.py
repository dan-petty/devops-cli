"""Tests for dry-run classifications across 20 local AI commands.

Issue #2247: The dry-run rule (#412) states that commands that make no external requests
are classified under the 'no-external-request' dry-run class.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from devops_cli.commands.ai import (
    ai_main,
    audit_library_usage_cmd,
    bundle_models,
    config,
    diagram_cmd,
    pack_context_cmd,
    read_cmd,
    repomap_cmd,
    spec_verify_cmd,
    token_count,
)
from devops_cli.commands.ai import (
    test_gen_cmd as cmd_test_gen,
)
from devops_cli.commands.ai_ast import (
    ast_graph_cmd,
    ast_parse_cmd,
)
from devops_cli.commands.ai_controller import (
    run_constellation_cmd,
    run_failover_cmd,
    run_quiesce_cmd,
    run_resume_cmd,
)
from devops_cli.commands.ai_harness import (
    harness_offload,
    harness_run,
    harness_status,
)
from devops_cli.dry_run import get_dry_run_class
from devops_cli.main import app

pytestmark = pytest.mark.usefixtures("keyring_store", "refuse_requests")

runner = CliRunner()

LOCAL_AI_COMMANDS: list[tuple[str, Any, list[str]]] = [
    ("ai", ai_main, ["--dry-run", "ai", "--help"]),
    (
        "ai ast graph",
        ast_graph_cmd,
        ["--dry-run", "ai", "ast", "graph", "--dir", "src/devops_cli/ai/ast"],
    ),
    ("ai ast parse", ast_parse_cmd, ["--dry-run", "ai", "ast", "parse", "src/devops_cli/main.py"]),
    ("ai audit-library-usage", audit_library_usage_cmd, ["--dry-run", "ai", "audit-library-usage"]),
    ("ai bundle-models", bundle_models, ["--dry-run", "ai", "bundle-models"]),
    ("ai config", config, ["--dry-run", "ai", "config"]),
    ("ai constellation", run_constellation_cmd, ["--dry-run", "ai", "constellation"]),
    ("ai diagram", diagram_cmd, ["--dry-run", "ai", "diagram"]),
    (
        "ai failover",
        run_failover_cmd,
        ["ai", "failover", "--target-provider", "ollama", "--dry-run"],
    ),
    ("ai harness offload", harness_offload, ["--dry-run", "ai", "harness", "offload"]),
    ("ai harness run", harness_run, ["--dry-run", "ai", "harness", "run", "inspect model"]),
    ("ai harness status", harness_status, ["--dry-run", "ai", "harness", "status"]),
    (
        "ai pack-context",
        pack_context_cmd,
        ["--dry-run", "ai", "pack-context", "src/devops_cli/main.py"],
    ),
    ("ai quiesce", run_quiesce_cmd, ["ai", "quiesce", "--dry-run"]),
    ("ai read", read_cmd, ["--dry-run", "ai", "read", "pyproject.toml"]),
    ("ai repomap", repomap_cmd, ["--dry-run", "ai", "repomap"]),
    ("ai resume", run_resume_cmd, ["ai", "resume", "--dry-run"]),
    ("ai spec", spec_verify_cmd, ["--dry-run", "ai", "spec"]),
    ("ai test-gen", cmd_test_gen, ["--dry-run", "ai", "test-gen", "src/devops_cli/main.py"]),
    ("ai token-count", token_count, ["--dry-run", "ai", "token-count", "pyproject.toml"]),
]


def test_dry_run_classes_decorated() -> None:
    """Verify that all 20 local AI command callbacks are decorated with no-external-request."""
    for name, callback, _ in LOCAL_AI_COMMANDS:
        assert get_dry_run_class(callback) == "no-external-request", (
            f"Expected {name} to have dry-run class 'no-external-request'"
        )


@pytest.mark.parametrize("name,callback,argv", LOCAL_AI_COMMANDS)
def test_local_ai_commands_run_cleanly(name: str, callback: Any, argv: list[str]) -> None:
    """Execute each local AI command under dry run and verify zero exit code."""
    result = runner.invoke(app, argv)
    assert result.exit_code == 0, f"{name} failed with exit {result.exit_code}: {result.output}"


def test_controller_commands_mutation_suppressed_in_dry_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that ai quiesce, ai failover, and ai resume do not write snapshot files under dry run."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(data_dir))

    snapshot_file = data_dir / "agent" / "quiesce.json"

    # 1. ai quiesce --dry-run
    res_quiesce = runner.invoke(app, ["ai", "quiesce", "--reason", "maintenance", "--dry-run"])
    assert res_quiesce.exit_code == 0
    assert not snapshot_file.exists(), "quiesce.json must not be created during dry run"

    # Global dry run
    res_quiesce_global = runner.invoke(app, ["--dry-run", "ai", "quiesce", "--reason", "global"])
    assert res_quiesce_global.exit_code == 0
    assert not snapshot_file.exists(), "quiesce.json must not be created during global dry run"

    # 2. ai failover --dry-run
    res_failover = runner.invoke(
        app, ["ai", "failover", "--target-provider", "ollama", "--dry-run"]
    )
    assert res_failover.exit_code == 0
    assert not snapshot_file.exists(), "quiesce.json must not be created during dry run"

    # 3. ai resume --dry-run
    res_resume = runner.invoke(app, ["ai", "resume", "--dry-run"])
    assert res_resume.exit_code == 0
    assert not snapshot_file.exists(), "quiesce.json must not be created during dry run"


READ_ONLY_COMMANDS = [
    ["ai", "ast", "graph", "--dry-run"],
    ["ai", "ast", "parse", "src/devops_cli/main.py", "--dry-run"],
    ["ai", "audit-library-usage", "--dry-run"],
    ["ai", "diagram", "--dry-run"],
    ["ai", "harness", "offload", "--dry-run"],
    ["ai", "harness", "run", "inspect model", "--dry-run"],
    ["ai", "pack-context", "src/devops_cli/main.py", "--dry-run"],
    ["ai", "read", "pyproject.toml", "--dry-run"],
    ["ai", "repomap", "--dry-run"],
    ["ai", "spec", "--dry-run"],
    ["ai", "test-gen", "src/devops_cli/main.py", "--dry-run"],
]


@pytest.mark.parametrize("argv", READ_ONLY_COMMANDS)
def test_read_only_commands_reject_subcommand_dry_run_option(argv: list[str]) -> None:
    """Verify that read-only commands without side effects reject --dry-run option."""
    result = runner.invoke(app, argv)
    assert result.exit_code == 2, f"Expected {argv} to fail with unrecognized option"
    assert (
        "No such option: --dry-run" in result.output
        or "no such option: --dry-run" in result.output.lower()
    )
