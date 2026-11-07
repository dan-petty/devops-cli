"""`devops roadmap plan-check`: its JSON output, its dry run and its exit code (#3201)."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime

import pytest
from typer.testing import CliRunner

from devops_cli.commands.roadmap import app
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.stage.stage_change import render_change
from tests.support.builders import make_stage_proposal
from tests.support.fakes.github import github_json, pull_request_payload
from tests.support.roadmap_stage import VALID_REPORT, StageRepo

REPO = "example/roadmap"
PULL = 7
ISSUE = 1
CHANGE = f"{ISSUE}-keep-the-last-comment"
CREATED = datetime(2026, 11, 4, tzinfo=UTC).date()
TITLE = "docs(openspec): plan #1 Stop the job dropping a comment"
BODY = "Plans #1\n\nThe job keeps every comment it reads.\n\nChange: `openspec/changes/1-keep-the-last-comment/`"
runner = CliRunner()


def _plan(repo: StageRepo, *, changes: str | None = None) -> str:
    files = render_change(CHANGE, make_stage_proposal(), {"comment-thread"}, created=CREATED)
    if changes is not None:
        tasks = f"openspec/changes/{CHANGE}/tasks.md"
        files[tasks] = re.sub(r"Changes: .*?\.\n", f"Changes: {changes}.\n", files[tasks], count=1)
    repo.git("switch", "-q", "-c", "plan")
    for path, text in files.items():
        (repo.clone / path).parent.mkdir(parents=True, exist_ok=True)
        (repo.clone / path).write_text(text, encoding="utf-8")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "plan")
    sha = repo.git("rev-parse", "HEAD")
    repo.git("push", "-q", "origin", f"HEAD:refs/pull/{PULL}/head")
    repo.git("switch", "-q", "main")
    return sha


def _routes(api, repo: StageRepo, head: str, *, title: str = TITLE, body: str = BODY) -> None:
    base = repo.git("rev-parse", "main")
    api.route(
        "GET",
        f"/repos/{REPO}/pulls/{PULL}",
        github_json(pull_request_payload(title=title, head_sha=head, base_sha=base)),
    )
    api.route(
        "GET",
        f"/repos/{REPO}/issues/{PULL}",
        github_json(
            {
                "number": PULL,
                "title": title,
                "state": "open",
                "body": body,
                "comments": 0,
                "labels": [],
                "pull_request": {"merged_at": None},
            }
        ),
    )
    api.route(
        "GET",
        f"/repos/{REPO}/issues/{ISSUE}",
        github_json({"number": ISSUE, "title": "An issue", "state": "open", "body": ""}),
    )
    api.route(
        "GET",
        f"/repos/{REPO}/commits/{head}/check-runs?per_page=100",
        github_json(
            {
                "check_runs": [
                    {"name": "Semantic PR title", "status": "completed", "conclusion": "success"}
                ]
            }
        ),
    )


@pytest.mark.usefixtures("openspec_fake")
def test_the_json_output_holds_each_problem_and_the_command_exits_one(
    stage_repo: StageRepo,
    github_api,
    openspec_fake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    head = _plan(stage_repo)
    _routes(github_api, stage_repo, head, title="feat(roadmap): add plan-check")
    openspec_fake.script(("validate", CHANGE, "--strict", "--json"), 0, VALID_REPORT)
    monkeypatch.chdir(stage_repo.clone)

    result = runner.invoke(
        app, ["plan-check", str(PULL), "--repo", REPO, "--json"], catch_exceptions=False
    )

    assert result.exit_code == 1, result.output
    (problem,) = json.loads(result.output)
    assert (problem["path"], problem["rule"], problem["message"]) == (
        "title",
        "title",
        MESSAGES.roadmap.plan_check_title.format(number=ISSUE),
    )


@pytest.mark.usefixtures("openspec_fake")
def test_the_dry_run_lists_the_reads_and_makes_none(
    stage_repo: StageRepo,
    github_api,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(stage_repo.clone)

    result = runner.invoke(
        app, ["plan-check", str(PULL), "--repo", REPO, "--dry-run"], catch_exceptions=False
    )

    assert result.exit_code == 0, result.output
    assert f"/repos/{REPO}/pulls/{PULL}" in result.output
    assert f"/repos/{REPO}/issues/<issue>" in result.output
    assert f"/repos/{REPO}/commits/<head>/check-runs" in result.output
    assert github_api.sent == []


@pytest.mark.usefixtures("openspec_fake")
def test_a_valid_plan_exits_zero_with_no_line(
    stage_repo: StageRepo,
    github_api,
    openspec_fake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    head = _plan(stage_repo)
    _routes(github_api, stage_repo, head)
    openspec_fake.script(("validate", CHANGE, "--strict", "--json"), 0, VALID_REPORT)
    monkeypatch.chdir(stage_repo.clone)

    result = runner.invoke(app, ["plan-check", str(PULL), "--repo", REPO], catch_exceptions=False)

    assert (result.exit_code, result.output) == (0, "")


@pytest.mark.usefixtures("openspec_fake")
@pytest.mark.parametrize(
    "changes",
    ["each module that names an old path", f"`openspec/changes/{CHANGE}/proposal.md`"],
    ids=["3187-no-file", "3308-change-folder"],
)
def test_a_plan_that_the_model_refuses_exits_one_with_a_read_problem_and_no_trace(
    stage_repo: StageRepo,
    github_api,
    openspec_fake,
    monkeypatch: pytest.MonkeyPatch,
    changes: str,
) -> None:
    head = _plan(stage_repo, changes=changes)
    _routes(github_api, stage_repo, head)
    openspec_fake.script(("validate", CHANGE, "--strict", "--json"), 0, VALID_REPORT)
    monkeypatch.chdir(stage_repo.clone)

    result = runner.invoke(
        app, ["plan-check", str(PULL), "--repo", REPO, "--json"], catch_exceptions=False
    )

    assert result.exit_code == 1, result.output
    (problem,) = json.loads(result.output)
    assert (problem["path"], problem["rule"]) == ("tasks.md", "read")
    assert "Traceback" not in result.output
