"""Unit tests for AI agent instruction generator and scaffolding utilities."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from devops_cli.ai.instruction_generator import (
    CONST_CLAUDE_MD_FILENAME,
    CONST_COPILOT_INSTRUCTIONS_PATH,
    ProjectMetadata,
    generate_agents_md,
    generate_pointer_stub,
    parse_project_metadata,
    scaffold_agent_instructions,
)
from devops_cli.commands.ai import app as ai_app
from devops_cli.commands.devcontainer import app as devcontainer_app
from devops_cli.config.constants import CONST_AGENTS_MD_FILENAME


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_parse_project_metadata_with_pyproject(tmp_path: Path) -> None:
    """Verify parse_project_metadata extracts accurate project details from pyproject.toml."""
    pyproject_toml = """\
[project]
name = "sample-service"
version = "1.2.3"
description = "High performance API gateway"
requires-python = ">=3.14"
dependencies = ["fastapi>=0.110.0"]

[project.scripts]
sample-service = "sample_service.cli:app"

[dependency-groups]
dev = ["pytest>=8.0.0", "ruff>=0.9.0"]
"""
    (tmp_path / "pyproject.toml").write_text(pyproject_toml, encoding="utf-8")

    meta = parse_project_metadata(tmp_path)
    assert meta.name == "sample-service"
    assert meta.version == "1.2.3"
    assert meta.description == "High performance API gateway"
    assert meta.requires_python == ">=3.14"
    assert "sample-service" in meta.entry_point
    assert "fastapi>=0.110.0" in meta.dependencies
    assert "pytest>=8.0.0" in meta.dev_dependencies
    assert not meta.is_devops_cli


def test_parse_project_metadata_fallback_when_no_pyproject(tmp_path: Path) -> None:
    """Verify fallback behavior when no pyproject.toml exists."""
    meta = parse_project_metadata(tmp_path)
    assert meta.name == tmp_path.name
    assert meta.version == "0.1.0"
    assert meta.requires_python == ">=3.14"


def test_generate_pointer_stub() -> None:
    """Verify pointer stubs correctly direct tools to canonical AGENTS.md."""
    claude_stub = generate_pointer_stub(
        title="Sample — Claude Instructions",
        tool_name="Claude Code",
        filename="CLAUDE.md",
        canonical_relpath="./AGENTS.md",
    )
    assert "# Sample — Claude Instructions" in claude_stub
    assert "Claude Code" in claude_stub
    assert "[AGENTS.md](./AGENTS.md)" in claude_stub
    assert "devops ai agents" in claude_stub


def test_generate_agents_md_contains_required_sections() -> None:
    """Verify generated AGENTS.md has standard sections and clean formatting."""
    meta = ProjectMetadata(
        name="test-automation",
        description="Workstation automation scripts",
        version="0.1.0",
        requires_python=">=3.14",
        entry_point="test-cli (test_automation.main:app)",
        has_devcontainer=True,
    )
    content = generate_agents_md(meta)

    assert "# test-automation — AI Agent Instructions & Engineering Best Practices" in content
    assert "Canonical Source" in content
    assert "## 1. Project Overview & Architecture" in content
    assert "## 2. Core Engineering Philosophy & Best Practices" in content
    assert "## 3. Build, Lint & Test Commands" in content
    assert "## 4. Git Hygiene & Branch Management" in content
    assert "uv sync" in content
    assert "uv run pytest" in content
    assert "uv run ruff check" in content
    assert "uv run mypy src" in content
    assert "DevContainer Environment" in content


def test_scaffold_agent_instructions(tmp_path: Path) -> None:
    """Verify scaffold_agent_instructions writes all default files."""
    written = scaffold_agent_instructions(tmp_path)
    assert len(written) == 3

    agents_md = tmp_path / CONST_AGENTS_MD_FILENAME
    claude_md = tmp_path / CONST_CLAUDE_MD_FILENAME
    copilot_md = tmp_path / CONST_COPILOT_INSTRUCTIONS_PATH

    assert agents_md.exists()
    assert claude_md.exists()
    assert copilot_md.exists()

    assert f"# {tmp_path.name}" in agents_md.read_text(encoding="utf-8")
    assert "Claude Code" in claude_md.read_text(encoding="utf-8")
    assert "GitHub Copilot" in copilot_md.read_text(encoding="utf-8")


def test_scaffold_agent_instructions_skip_existing_without_force(tmp_path: Path) -> None:
    """Verify existing files are not overwritten unless force=True."""
    agents_md = tmp_path / CONST_AGENTS_MD_FILENAME
    agents_md.write_text("Custom instruction content", encoding="utf-8")

    # Call without force
    written = scaffold_agent_instructions(tmp_path, force=False)
    assert agents_md not in written
    assert agents_md.read_text(encoding="utf-8") == "Custom instruction content"

    # Call with force
    written_force = scaffold_agent_instructions(tmp_path, force=True)
    assert agents_md in written_force
    assert "Canonical Source" in agents_md.read_text(encoding="utf-8")


def test_devcontainer_init_scaffolds_agent_instructions(runner: CliRunner, tmp_path: Path) -> None:
    """Verify devops devcontainer init scaffolds AGENTS.md, CLAUDE.md, and copilot instructions."""
    result = runner.invoke(devcontainer_app, ["init", str(tmp_path), "--name", "init-test-proj"])
    assert result.exit_code == 0

    assert (tmp_path / ".devcontainer" / "devcontainer.json").exists()
    assert (tmp_path / ".vscode" / "mcp.json").exists()
    assert (tmp_path / "AGENTS.md").exists()
    assert (tmp_path / "CLAUDE.md").exists()
    assert (tmp_path / ".github" / "copilot-instructions.md").exists()


def test_devcontainer_post_create_scaffolds_agent_instructions(
    runner: CliRunner, tmp_path: Path
) -> None:
    """Verify devops devcontainer post-create scaffolds missing agent instructions."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "post-create-proj"\n', encoding="utf-8"
    )

    # Dry-run test
    res_dry = runner.invoke(
        devcontainer_app,
        ["post-create", "--workspace", str(tmp_path), "--dry-run"],
    )
    assert res_dry.exit_code == 0

    # Live execution test
    res_live = runner.invoke(
        devcontainer_app,
        ["post-create", "--workspace", str(tmp_path)],
    )
    assert res_live.exit_code == 0
    assert (tmp_path / "AGENTS.md").exists()
    assert (tmp_path / "CLAUDE.md").exists()
    assert (tmp_path / ".github" / "copilot-instructions.md").exists()


def test_ai_agents_command_scaffolds_instructions(runner: CliRunner, tmp_path: Path) -> None:
    """Verify devops ai agents command scaffolds files in target repository."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "ai-test-proj"\ndescription = "Testing AI agents generation"',
        encoding="utf-8",
    )

    result = runner.invoke(ai_app, ["agents", "--repo", str(tmp_path), "--template"])
    assert result.exit_code == 0

    assert (tmp_path / "AGENTS.md").exists()
    assert (tmp_path / "CLAUDE.md").exists()
    assert (tmp_path / ".github" / "copilot-instructions.md").exists()
    assert "Testing AI agents generation" in (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
