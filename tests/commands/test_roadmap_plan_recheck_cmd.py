"""`devops roadmap plan-recheck`: its dry run and its JSON output (#3492)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from devops_cli.commands.roadmap import app
from devops_cli.roadmap.stage_change import render_change
from tests.support.builders import make_stage_proposal
from tests.support.roadmap_stage import VALID_REPORT, StageRepo, validate_args

if TYPE_CHECKING:
    from click.testing import Result

    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.openspec import OpenSpecFake

REPO = "example/roadmap"
CHANGE = "1-keep-the-last-comment"
ROOT = f"openspec/changes/{CHANGE}"
TASKS = f"{ROOT}/tasks.md"
DESIGN = f"{ROOT}/design.md"
runner = CliRunner()


def _old_plan() -> dict[str, str]:
    """A merged plan that the rewrite fixes: no `Verification:` line and no `design.md`."""
    files = render_change(
        CHANGE,
        make_stage_proposal(),
        {"comment-thread"},
        created=datetime(2026, 11, 4, tzinfo=UTC).date(),
    )
    del files[DESIGN]
    kept = [line for line in files[TASKS].splitlines(keepends=True) if "Verification:" not in line]
    files[TASKS] = "".join(kept)
    return files


def _confirm(repo: StageRepo, *extra: str) -> Result:
    args = ["plan-recheck", "--repo", REPO, "--source", str(repo.clone), "--confirm", *extra]
    return runner.invoke(app, args, catch_exceptions=False)


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


@pytest.mark.usefixtures("openspec_fake", "roadmap_store")
def test_the_json_output_holds_the_folders_and_the_counts(
    stage_repo: StageRepo, monkeypatch: pytest.MonkeyPatch
) -> None:
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


@pytest.mark.usefixtures("roadmap_store")
def test_the_json_output_of_a_branch_run_holds_the_comparison(
    stage_repo: StageRepo, openspec_fake: OpenSpecFake, monkeypatch: pytest.MonkeyPatch
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
    openspec_fake.script(validate_args(CHANGE), 0, VALID_REPORT)
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


@pytest.fixture
def rewrite_repo(
    stage_repo: StageRepo, openspec_fake: OpenSpecFake, monkeypatch: pytest.MonkeyPatch
) -> StageRepo:
    """A checkout that tracks a plan which the rewrite fixes; the OpenSpec check accepts it."""
    stage_repo.track(_old_plan())
    openspec_fake.script(validate_args(CHANGE), 0, VALID_REPORT)
    monkeypatch.chdir(stage_repo.clone)
    return stage_repo


@pytest.mark.usefixtures("roadmap_store")
def test_a_run_without_confirm_reports_the_rewrite_and_writes_nothing(
    rewrite_repo: StageRepo,
) -> None:
    result = runner.invoke(
        app,
        ["plan-recheck", "--repo", REPO, "--source", str(rewrite_repo.clone)],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    assert f"rewrite {CHANGE}" in result.output
    assert rewrite_repo.git("status", "--porcelain") == ""


@pytest.mark.usefixtures("roadmap_store")
def test_confirm_writes_the_changed_files_of_each_rewrite_folder_and_makes_no_commit(
    rewrite_repo: StageRepo,
) -> None:
    head = rewrite_repo.git("rev-parse", "HEAD")

    result = _confirm(rewrite_repo)

    assert result.exit_code == 0, result.output
    assert rewrite_repo.git("rev-parse", "HEAD") == head
    status = rewrite_repo.git("status", "--porcelain")
    assert sorted(line.split()[-1] for line in status.splitlines()) == [DESIGN, TASKS]
    # The rewrite only adds lines: it keeps the line end at the end of the file.
    assert rewrite_repo.git("diff", "--numstat", "--", TASKS).split()[1] == "0"
    assert "Verification:" in (rewrite_repo.clone / TASKS).read_text(encoding="utf-8")
    assert "Changed 2 files" in result.output


@pytest.mark.usefixtures("roadmap_store")
def test_a_second_confirm_finds_nothing_to_rewrite(rewrite_repo: StageRepo) -> None:
    assert _confirm(rewrite_repo).exit_code == 0
    rewrite_repo.git("add", "-A")
    rewrite_repo.git("commit", "-q", "-m", "rewrite")
    rewrite_repo.git("push", "-q", "origin", "main")

    result = _confirm(rewrite_repo)

    assert result.exit_code == 0, result.output
    assert f"ok {CHANGE}" in result.output
    assert "Changed" not in result.output


@pytest.mark.usefixtures("roadmap_store")
def test_confirm_without_source_is_an_error_that_names_the_option(
    rewrite_repo: StageRepo,
) -> None:
    result = runner.invoke(app, ["plan-recheck", "--repo", REPO, "--confirm"])

    assert result.exit_code == 1
    assert "--source" in result.output
    assert rewrite_repo.git("status", "--porcelain") == ""


@pytest.mark.usefixtures("roadmap_store")
def test_confirm_with_dry_run_is_an_error(rewrite_repo: StageRepo) -> None:
    result = _confirm(rewrite_repo, "--dry-run")

    assert result.exit_code == 1
    assert "--dry-run" in result.output
    assert "--confirm" in result.output
    assert rewrite_repo.git("status", "--porcelain") == ""


@pytest.mark.usefixtures("roadmap_store")
def test_a_file_that_differs_from_the_default_branch_stops_the_write_before_any_file(
    rewrite_repo: StageRepo,
) -> None:
    (rewrite_repo.clone / DESIGN).write_text("# My own design\n", encoding="utf-8")
    before = rewrite_repo.git("status", "--porcelain")

    result = _confirm(rewrite_repo)

    assert result.exit_code == 1
    assert DESIGN in result.output
    assert rewrite_repo.git("status", "--porcelain") == before
    assert "Verification:" not in (rewrite_repo.clone / TASKS).read_text(encoding="utf-8")
    assert (rewrite_repo.clone / DESIGN).read_text(encoding="utf-8") == "# My own design\n"
