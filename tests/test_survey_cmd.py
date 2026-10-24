"""Tests for the devops survey command, report formats, and intake integration."""

from __future__ import annotations

import json
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from devops_cli.survey.models import CapabilityGap, CapabilityStatus


def test_survey_command_json_output(cli: Callable[..., Any]) -> None:
    """The survey command runs and emits a structured JSON report to stdout."""
    result = cli("survey", "--json", "--dependencies-only")
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert "dependencies" in payload
    assert isinstance(payload["dependencies"], list)
    assert len(payload["dependencies"]) >= 30
    first = payload["dependencies"][0]
    assert "name" in first
    assert "last_commit_date" in first
    assert "release_cadence" in first
    assert "archival_status" in first
    assert "licence" in first


def test_survey_command_table_output(cli: Callable[..., Any]) -> None:
    """The survey command runs with default table output and exits 0."""
    result = cli("survey", "--dependencies-only")
    assert result.exit_code == 0
    assert "Dependencies" in result.output or "Dependency" in result.output


def test_survey_command_with_custom_config(cli: Callable[..., Any]) -> None:
    """The survey command evaluates capabilities from a custom configuration file."""
    config_toml = """
    [[tools]]
    name = "custom-cli"
    description = "A custom comparable tool"
    url = "https://example.com/custom-cli"

    [[capabilities]]
    name = "custom-feature"
    description = "A specific feature"
    devops_cli = "absent"
    citation = "N/A"

    [[capabilities.comparable]]
    tool = "custom-cli"
    status = "present"
    citation = "https://example.com/custom-cli/feature"

    [[capabilities]]
    name = "unassessed-item"
    description = "An item without assessment"
    devops_cli = "present"
    citation = "internal"
    """
    with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as f:
        f.write(config_toml)
        config_path = Path(f.name)

    try:
        result = cli("survey", "--capabilities-only", "--config", str(config_path), "--json")
        assert result.exit_code == 0
        data = json.loads(result.output)
        caps = data.get("capabilities", [])
        assert len(caps) == 2

        gap_row = next(c for c in caps if c["capability"] == "custom-feature")
        assert gap_row["devops_cli_status"] == CapabilityStatus.ABSENT.value
        assert gap_row["tool_status"] == CapabilityStatus.PRESENT.value
        assert gap_row["citation"] == "https://example.com/custom-cli/feature"
        assert gap_row["is_gap"] is True

        unassessed_row = next(c for c in caps if c["capability"] == "unassessed-item")
        assert unassessed_row["tool_status"] == CapabilityStatus.UNKNOWN.value
        assert unassessed_row["tool_status"] != CapabilityStatus.ABSENT.value
        assert unassessed_row["citation"] != ""
    finally:
        config_path.unlink(missing_ok=True)


def test_survey_emit_candidates_calls_intake(cli: Callable[..., Any]) -> None:
    """The survey command hands discovered capability gaps to roadmap intake."""
    config_toml = """
    [[tools]]
    name = "tool-x"
    description = "Tool X"
    url = "https://example.com/tool-x"

    [[capabilities]]
    name = "missing-capability"
    description = "A missing capability that should become a candidate"
    devops_cli = "absent"
    citation = "N/A"

    [[capabilities.comparable]]
    tool = "tool-x"
    status = "present"
    citation = "https://example.com/tool-x/docs"
    """
    with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as f:
        f.write(config_toml)
        config_path = Path(f.name)

    try:
        with patch("devops_cli.commands.survey.emit_all_gaps_to_intake") as mock_emit:
            mock_emit.return_value = [MagicMock(number=999, decision=MagicMock(outcome="place"))]
            result = cli(
                "survey",
                "--capabilities-only",
                "--config",
                str(config_path),
                "--emit-candidates",
                "--confirm",
            )
            assert result.exit_code == 0
            assert mock_emit.called
            gaps_arg = mock_emit.call_args[0][0]
            assert len(gaps_arg) == 1
            gap = gaps_arg[0]
            assert isinstance(gap, CapabilityGap)
            assert gap.capability == "missing-capability"
            assert gap.tool == "tool-x"
            assert gap.citation == "https://example.com/tool-x/docs"
    finally:
        config_path.unlink(missing_ok=True)
