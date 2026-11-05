"""`devops roadmap plan-recheck`: its dry run and its JSON output (#3492)."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from devops_cli.commands import roadmap as roadmap_commands
from devops_cli.commands.roadmap import app
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from tests.support.roadmap_stage import StageRepo

REPO = "example/roadmap"
runner = CliRunner()


def test_the_dry_run_lists_the_reads_and_makes_none(
    stage_repo: StageRepo, github_api, monkeypatch: pytest.MonkeyPatch
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
