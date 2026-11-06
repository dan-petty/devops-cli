"""`devops roadmap plan-recheck`: its dry run and its JSON output (#3492)."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest
from typer.testing import CliRunner

from devops_cli.commands import roadmap as roadmap_commands
from devops_cli.commands.roadmap import app
from devops_cli.openspec import tool as openspec_tool
from devops_cli.openspec.tool import OpenSpecTool
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.stage_change import render_change
from tests.support.builders import make_stage_proposal
from tests.support.roadmap_stage import VALID_REPORT, StageRepo

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake

REPO = "example/roadmap"
CHANGE = "1-keep-the-last-comment"
runner = CliRunner()


class _AcceptingTool:
    """An OpenSpec that accepts every change."""

    def run(self, args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        del args, cwd
        return subprocess.CompletedProcess([], 0, VALID_REPORT, "")


@contextmanager
def _accepting_openspec() -> Iterator[OpenSpecTool]:
    yield cast("OpenSpecTool", _AcceptingTool())


def test_the_dry_run_lists_the_reads_and_makes_none(
    stage_repo: StageRepo, github_api: GitHubApiFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(stage_repo.clone)

    result = runner.invoke(
        app, ["plan-recheck", "--repo", REPO, "--dry-run"], catch_exceptions=False
    )

    assert result.exit_code == 0, result.output
    assert "ls-tree" in result.output
    assert f"/repos/{REPO}/issues" in result.output
    assert github_api.sent == []


@pytest.mark.usefixtures("openspec_fake")
def test_the_json_output_holds_the_folders_and_the_counts(
    stage_repo: StageRepo, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = InMemoryRoadmapStore()
    monkeypatch.setattr(roadmap_commands, "_open_store", lambda repo: (None, store))
    monkeypatch.chdir(stage_repo.clone)

    result = runner.invoke(
        app,
        ["plan-recheck", "--repo", REPO, "--source", str(stage_repo.clone), "--json"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report["folders"] == []
    assert report["summary"]["live"] == 0


def test_the_dry_run_of_a_branch_run_lists_the_reads_of_the_branch(
    stage_repo: StageRepo, github_api: GitHubApiFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(stage_repo.clone)

    result = runner.invoke(
        app,
        ["plan-recheck", "--repo", REPO, "--branch", "origin/topic", "--dry-run"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    assert "ls-tree -r --name-only origin/topic" in result.output
    assert "origin/topic:openspec/changes/" in result.output
    assert github_api.sent == []


def test_the_json_output_of_a_branch_run_holds_the_comparison(
    stage_repo: StageRepo, monkeypatch: pytest.MonkeyPatch
) -> None:
    group = make_stage_proposal().groups[0].model_copy(update={"reads": ["src/devops_cli/gone.py"]})
    plan = render_change(
        CHANGE,
        make_stage_proposal(groups=[group]),
        {"comment-thread"},
        created=datetime(2026, 11, 4, tzinfo=UTC).date(),
    )
    stage_repo.git("switch", "-q", "-c", "topic")
    for name, text in plan.items():
        (stage_repo.clone / name).parent.mkdir(parents=True, exist_ok=True)
        (stage_repo.clone / name).write_text(text, encoding="utf-8")
    stage_repo.git("add", "-A")
    stage_repo.git("commit", "-q", "-m", "plan")
    stage_repo.git("switch", "-q", "main")
    monkeypatch.setattr(
        roadmap_commands, "_open_store", lambda repo: (None, InMemoryRoadmapStore())
    )
    monkeypatch.setattr(openspec_tool, "isolated_openspec", _accepting_openspec)
    monkeypatch.chdir(stage_repo.clone)

    result = runner.invoke(
        app,
        [
            "plan-recheck",
            "--repo",
            REPO,
            "--source",
            str(stage_repo.clone),
            "--branch",
            "topic",
            "--json",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report["folders"] == []
    assert report["gates"] == {}
    branch = report["branch"]
    assert branch["ref"] == "topic"
    assert [folder["folder"] for folder in branch["folders"]] == [CHANGE]
    assert branch["gates"] == {"paths": 1}
    assert [(r["folder"], r["gate"], r["label"]) for r in branch["new_refusals"]] == [
        (CHANGE, "paths", "case to review")
    ]
    assert branch["not_read"] == []
