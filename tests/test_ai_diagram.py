"""Tests for architecture topology and threat modeling diagram generator."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from devops_cli.ai.diagram import generate_architecture_diagram, generate_threat_diagram
from devops_cli.commands.ai import app as ai_app

runner = CliRunner()


def test_diagram_generation() -> None:
    """Verify architecture and threat modeling diagram generators."""
    arch = generate_architecture_diagram()
    assert arch.diagram_type == "arch"
    assert "graph TD" in arch.mermaid_code

    threat = generate_threat_diagram()
    assert threat.diagram_type == "threat"
    assert "graph LR" in threat.mermaid_code


def test_diagram_cli() -> None:
    """Verify devops ai diagram CLI command."""
    res_arch = runner.invoke(ai_app, ["diagram", "arch", "--dry-run"])
    assert res_arch.exit_code == 0
    assert "DRY_RUN_DIAGRAM_GENERATED" in res_arch.output

    res_threat = runner.invoke(ai_app, ["diagram", "threat", "--json"])
    assert res_threat.exit_code == 0
    data = json.loads(res_threat.output)
    assert data["diagram_type"] == "threat"
