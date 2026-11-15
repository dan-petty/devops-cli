"""Tests for devops ai agent-audit command (#2346)."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from devops_cli.ai.agent_audit.filing import FiledIssue


def _tool_call(command: str) -> list[dict[str, Any]]:
    return [
        {
            "type": "assistant",
            "timestamp": "2026-01-01T00:00:00.000Z",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_01",
                        "name": "Bash",
                        "input": {"command": command},
                    }
                ],
            },
        },
        {
            "type": "user",
            "timestamp": "2026-01-01T00:00:01.000Z",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_01",
                        "is_error": True,
                        "content": "Exit code 1\nfailed check",
                    }
                ],
            },
        },
    ]


def _setup_fixture_repo(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    home = tmp_path / "home"
    projects = home / ".claude" / "projects"

    import re

    slug = re.sub(r"[^A-Za-z0-9]", "-", str(repo.resolve()))
    session_file = projects / slug / "session.jsonl"
    session_file.parent.mkdir(parents=True)

    records = _tool_call("uv run devops ci test")
    with session_file.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")

    return repo, home


def test_confirm_calls_file_drafts_once(
    cli: Callable[..., Any],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A run with --confirm calls file_drafts once with the drafted groups (#2346)."""
    repo, home = _setup_fixture_repo(tmp_path)
    monkeypatch.setenv("HOME", str(home))

    mock_file = MagicMock(return_value=(FiledIssue(title="fix(ai): failed check", number=42),))
    from devops_cli.commands import ai_agent_audit

    monkeypatch.setattr(ai_agent_audit, "file_drafts", mock_file)
    monkeypatch.setattr(
        ai_agent_audit,
        "group_findings",
        lambda findings: tuple(replace(f, group="failed check") for f in findings),
    )

    res = cli("ai", "agent-audit", "--repo-dir", str(repo), "--confirm")
    assert res.exit_code == 0
    assert mock_file.call_count == 1
    assert "Filed #42" in res.stdout


def test_dry_run_with_confirm_is_refused(
    cli: Callable[..., Any],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """--dry-run combined with --confirm is refused with a usage error (#2346)."""
    repo, home = _setup_fixture_repo(tmp_path)
    monkeypatch.setenv("HOME", str(home))

    from devops_cli.commands import ai_agent_audit

    mock_file = MagicMock()
    monkeypatch.setattr(ai_agent_audit, "file_drafts", mock_file)

    res = cli("ai", "agent-audit", "--repo-dir", str(repo), "--dry-run", "--confirm")
    assert res.exit_code != 0
    assert mock_file.call_count == 0


def test_dry_run_makes_no_requests_and_reads_transcripts(
    cli: Callable[..., Any],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A run with --dry-run reads the transcripts and outputs the findings without external calls (#2346)."""
    repo, home = _setup_fixture_repo(tmp_path)
    monkeypatch.setenv("HOME", str(home))

    from devops_cli.commands import ai_agent_audit

    mock_group = MagicMock()
    mock_file = MagicMock()
    monkeypatch.setattr(ai_agent_audit, "group_findings", mock_group)
    monkeypatch.setattr(ai_agent_audit, "file_drafts", mock_file)

    res = cli("ai", "agent-audit", "--repo-dir", str(repo), "--dry-run")
    assert res.exit_code == 0
    assert mock_group.call_count == 0
    assert mock_file.call_count == 0
    assert "Recurring problems" in res.stdout
    assert "uv run devops ci test" in res.stdout


def test_json_output(
    cli: Callable[..., Any],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The --json flag formats the output as JSON (#2346)."""
    repo, home = _setup_fixture_repo(tmp_path)
    monkeypatch.setenv("HOME", str(home))

    res = cli("ai", "agent-audit", "--repo-dir", str(repo), "--dry-run", "--json")
    assert res.exit_code == 0
    data = json.loads(res.stdout)
    assert isinstance(data, dict)
    assert "findings" in data
    assert len(data["findings"]) == 1
    assert data["findings"][0]["sessions"] == 1


def test_source_shell(
    cli: Callable[..., Any],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The --source shell option reads zsh history (#2346)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    history = home / ".zsh_history"
    history.write_text(": 1700000000:0;git checkout main\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))

    res = cli("ai", "agent-audit", "--repo-dir", str(repo), "--source", "shell", "--dry-run")
    assert res.exit_code == 0
    assert "git checkout main" in res.stdout


def test_source_files(
    cli: Callable[..., Any],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The --source files option reads agent files (#2346)."""
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    agent_dir = repo / ".data" / "agent" / "logs"
    agent_dir.mkdir(parents=True)
    (agent_dir / "test.log").write_text("uv run pytest\nwarning: missing file\n", encoding="utf-8")

    res = cli("ai", "agent-audit", "--repo-dir", str(repo), "--source", "files", "--dry-run")
    assert res.exit_code == 0
    assert "warning: missing file" in res.stdout
