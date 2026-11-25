"""`devops roadmap plan-recheck`: its dry run, its JSON output and its open plan branches
(#3492, #3969)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from devops_cli.commands.roadmap import app
from devops_cli.roadmap.stage.stage_change import render_change
from devops_cli.roadmap.stores.store import ItemField, install_roadmap_store
from tests.support.builders import make_stage_proposal
from tests.support.fakes.github import github_json, pull_request_payload
from tests.support.roadmap_stage import VALID_REPORT, StageRepo, validate_args

if TYPE_CHECKING:
    from click.testing import Result

    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.openspec import OpenSpecFake
    from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

REPO = "example/roadmap"
CHANGE = "1-keep-the-last-comment"
ROOT = f"openspec/changes/{CHANGE}"
TASKS = f"{ROOT}/tasks.md"
DESIGN = f"{ROOT}/design.md"
ISSUE = 1
BRANCH = "docs/1-keep-the-last-comment"
AHEAD = "docs/1-ahead"
PLAN_TITLE = f"docs(spec): plan #{ISSUE} Keep the last comment"
PLAN_BODY = f"Plans #{ISSUE}"
runner = CliRunner()


def _plan() -> dict[str, str]:
    """The stock plan of the item, which the mechanical rewrite leaves as it is."""
    return render_change(
        CHANGE,
        make_stage_proposal(),
        {"comment-thread"},
        created=datetime(2026, 11, 4, tzinfo=UTC).date(),
    )


def _old_plan() -> dict[str, str]:
    """A merged plan that the rewrite fixes: no `Verification:` line and no `design.md`."""
    files = _plan()
    del files[DESIGN]
    kept = [line for line in files[TASKS].splitlines(keepends=True) if "Verification:" not in line]
    files[TASKS] = "".join(kept)
    return files


def _push(repo: StageRepo, branch: str, files: Mapping[str, str]) -> None:
    """Commit `files` on `branch` of `origin`, from `main`, and leave the clone on `main`."""
    repo.git("switch", "-q", "-c", branch)
    for path, text in files.items():
        target = repo.clone / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", f"plan on {branch}")
    repo.git("push", "-q", "origin", branch)
    repo.git("switch", "-q", "main")


def _seed_pull(store: InMemoryRoadmapStore, branch: str) -> int:
    """An open draft plan pull request on `branch`, with the number it got."""
    return store.seed_pull(PLAN_TITLE, head_ref=branch, draft=True)


def _route_pull(
    api: GitHubApiFake,
    repo: StageRepo,
    number: int,
    *,
    title: str = PLAN_TITLE,
    body: str = PLAN_BODY,
) -> None:
    """The reads of the facts of the pull request `number`: its head and its body."""
    base = repo.git("rev-parse", "main")
    api.route(
        "GET",
        f"/repos/{REPO}/pulls/{number}",
        github_json(pull_request_payload(title=title, head_sha="a" * 40, base_sha=base)),
    )
    api.route(
        "GET",
        f"/repos/{REPO}/issues/{number}",
        github_json(
            {
                "number": number,
                "title": title,
                "state": "open",
                "body": body,
                "comments": 0,
                "labels": [],
                "pull_request": {"merged_at": None},
            }
        ),
    )


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


def _branches(stage_repo: StageRepo, *extra: str) -> Result:
    args = ["plan-recheck", "--repo", REPO, "--source", str(stage_repo.clone), "--branches", *extra]
    return runner.invoke(app, args, catch_exceptions=False)


@pytest.mark.usefixtures("openspec_fake")
def test_each_open_plan_branch_is_judged(
    stage_repo: StageRepo,
    github_api: GitHubApiFake,
    roadmap_store: InMemoryRoadmapStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`--branches` prints one result for each open draft plan pull request: the branch whose plan
    the rewrite changes is `rewritten`, the branch it leaves is `unchanged`, and a run without
    `--confirm` pushes neither."""
    stage_repo.track(_plan())
    stage_repo.push_branch(BRANCH)
    _push(stage_repo, AHEAD, _old_plan())
    same = _seed_pull(roadmap_store, BRANCH)
    changed = _seed_pull(roadmap_store, AHEAD)
    for number in (same, changed):
        _route_pull(github_api, stage_repo, number)
    before = stage_repo.origin_git("rev-parse", f"refs/heads/{AHEAD}")
    monkeypatch.chdir(stage_repo.clone)

    result = _branches(stage_repo)

    assert result.exit_code == 0, result.output
    assert f"Pull request #{same} on `{BRANCH}`: unchanged." in result.output
    assert f"Pull request #{changed} on `{AHEAD}`: rewritten." in result.output
    assert f"  changes `{TASKS}`" in result.output
    assert "2 open plan branches: 1 rewritten, 1 unchanged, 0 conflict, 0 invalid." in result.output
    assert stage_repo.origin_git("rev-parse", f"refs/heads/{AHEAD}") == before


@pytest.mark.usefixtures("openspec_fake")
def test_a_delivery_branch_is_left_out(
    stage_repo: StageRepo,
    github_api: GitHubApiFake,
    roadmap_store: InMemoryRoadmapStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A draft pull request that the implement job took over as the delivery of the item is no
    plan branch, so the run gives it no result."""
    stage_repo.track(_plan())
    stage_repo.push_branch(BRANCH)
    plan = _seed_pull(roadmap_store, BRANCH)
    delivery = roadmap_store.seed_pull(
        "feat(roadmap): deliver the plan", head_ref="feat/2-deliver", draft=True
    )
    _route_pull(github_api, stage_repo, plan)
    _route_pull(
        github_api,
        stage_repo,
        delivery,
        title="feat(roadmap): deliver the plan",
        body="Closes #2",
    )
    monkeypatch.chdir(stage_repo.clone)

    result = _branches(stage_repo)

    assert result.exit_code == 0, result.output
    assert f"Pull request #{plan} on `{BRANCH}`" in result.output
    assert f"Pull request #{delivery}" not in result.output
    assert "1 open plan branches:" in result.output


def test_the_branches_dry_run_lists_the_reads(github_api: GitHubApiFake) -> None:
    """The dry run of `--branches` lists the reads of the pass and the writes of a confirmed push,
    and it makes no request."""
    result = runner.invoke(
        app, ["plan-recheck", "--repo", REPO, "--dry-run", "--branches"], catch_exceptions=False
    )

    assert result.exit_code == 0, result.output
    assert f"/repos/{REPO}/pulls" in result.output
    assert "ls-tree -r --name-only origin/main" in result.output
    assert "fetch -q origin '<branch>' main" in result.output
    assert "worktree add --detach" in result.output
    assert "--force-with-lease=refs/heads/<branch>:<head>" in result.output
    assert github_api.sent == []


@pytest.mark.usefixtures("roadmap_store")
def test_confirm_pushes_the_rewritten_branch_once(
    stage_repo: StageRepo,
    github_api: GitHubApiFake,
    openspec_fake: OpenSpecFake,
    roadmap_store: InMemoryRoadmapStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With `--confirm`, the command rebases, rewrites and pushes the branch whose plan the rewrite
    changes, as one commit."""
    stage_repo.track(_plan())
    _push(stage_repo, AHEAD, _old_plan())
    number = _seed_pull(roadmap_store, AHEAD)
    _route_pull(github_api, stage_repo, number)
    openspec_fake.script(validate_args(CHANGE), 0, VALID_REPORT)
    before = stage_repo.origin_git("rev-parse", f"refs/heads/{AHEAD}")
    monkeypatch.chdir(stage_repo.clone)

    result = _branches(stage_repo, "--confirm")

    assert result.exit_code == 0, result.output
    assert f"Pull request #{number} on `{AHEAD}`: rewritten." in result.output
    after = stage_repo.origin_git("rev-parse", f"refs/heads/{AHEAD}")
    assert after != before
    assert stage_repo.origin_git("rev-list", "--count", f"{before}..{after}") == "1"


def test_the_branches_option_takes_no_branch(stage_repo: StageRepo) -> None:
    """`--branches` reads the open plan branches itself, so it refuses `--branch`."""
    result = _branches(stage_repo, "--branch", "topic")

    assert result.exit_code == 1
    assert "takes no --branch" in result.output


def test_the_branches_option_takes_no_json(stage_repo: StageRepo) -> None:
    """The pass prints one line for each open plan branch, so it refuses `--json`."""
    result = _branches(stage_repo, "--json")

    assert result.exit_code == 1
    assert "takes no --json" in result.output


# A run with a base, a candidate and an issue listing (#6705): the check of the stage agent.
MISSING_READ = "src/devops_cli/missing.py"
ISSUE_TITLE = "fix(roadmap): keep the last comment"


def _refused_plan() -> dict[str, str]:
    """The stock plan of the item, whose group reads a file that no commit holds."""
    group = make_stage_proposal().groups[0].model_copy(update={"reads": [MISSING_READ]})
    return render_change(
        CHANGE,
        make_stage_proposal(groups=[group]),
        {"comment-thread"},
        created=datetime(2026, 11, 4, tzinfo=UTC).date(),
    )


def _base_branch(repo: StageRepo, files: Mapping[str, str]) -> str:
    """Commit `files` on the local branch `topic` from `main`, and give the commit of `main`."""
    base = repo.git("rev-parse", "main")
    repo.git("switch", "-q", "-c", "topic")
    for path, text in files.items():
        (repo.clone / path).parent.mkdir(parents=True, exist_ok=True)
        (repo.clone / path).write_text(text, encoding="utf-8")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "plan")
    repo.git("switch", "-q", "main")
    return base


def _base_run(repo: StageRepo, base: str, *extra: str) -> Result:
    args = [
        "plan-recheck",
        "--repo",
        REPO,
        "--source",
        str(repo.clone),
        "--branch",
        "topic",
        "--base",
        base,
        *extra,
    ]
    return runner.invoke(app, args, catch_exceptions=False)


@pytest.fixture
def base_repo(
    stage_repo: StageRepo, openspec_fake: OpenSpecFake, monkeypatch: pytest.MonkeyPatch
) -> StageRepo:
    """A clone whose `origin` refuses each fetch; the OpenSpec check accepts the change."""
    openspec_fake.script(validate_args(CHANGE), 0, VALID_REPORT)
    stage_repo.git("remote", "set-url", "origin", str(stage_repo.clone.parent / "gone.git"))
    monkeypatch.chdir(stage_repo.clone)
    return stage_repo


def test_a_base_run_exits_1_for_a_refused_folder_of_the_branch(
    base_repo: StageRepo, roadmap_store: InMemoryRoadmapStore
) -> None:
    roadmap_store.seed_issue(ISSUE_TITLE, fields={ItemField.PRIORITY: "P1-High"})
    base = _base_branch(base_repo, _refused_plan())

    result = _base_run(base_repo, base)

    assert result.exit_code == 1, result.output
    assert f"new-plan {CHANGE}" in result.output
    assert f"Folders of `topic` that are not ok against the base {base}: {CHANGE}." in result.output


def test_a_base_run_puts_the_failed_folders_in_the_json_of_the_branch(
    base_repo: StageRepo, roadmap_store: InMemoryRoadmapStore
) -> None:
    roadmap_store.seed_issue(ISSUE_TITLE, fields={ItemField.PRIORITY: "P1-High"})
    base = _base_branch(base_repo, _refused_plan())

    result = _base_run(base_repo, base, "--json")

    assert result.exit_code == 1
    report = json.loads(result.output)
    assert report["folders"] == []
    assert report["branch"]["failed"] == [CHANGE]
    assert "paths" in report["branch"]["gates"]


def test_a_run_with_a_listing_opens_no_store(
    base_repo: StageRepo, roadmap_store: InMemoryRoadmapStore, tmp_path: Path
) -> None:
    roadmap_store.seed_issue(ISSUE_TITLE, fields={ItemField.PRIORITY: "P1-High"})
    base = _base_branch(base_repo, _plan())
    by_store = _base_run(base_repo, base, "--json")
    listing = tmp_path / "issues.json"
    listing.write_text(
        json.dumps([{"number": ISSUE, "title": ISSUE_TITLE, "url": "u"}]),
        encoding="utf-8",
    )
    opened: list[str] = []

    def refuse(repo: str, **_: object) -> InMemoryRoadmapStore:
        opened.append(repo)
        raise AssertionError("the run opened a store")

    install_roadmap_store(refuse)

    by_listing = _base_run(base_repo, base, "--json", "--issues", str(listing))

    assert by_listing.exit_code == by_store.exit_code == 0, by_listing.output
    assert json.loads(by_listing.output) == json.loads(by_store.output)
    assert opened == []


def test_the_dry_run_of_a_base_and_a_listing_lists_no_issue_read_and_no_fetch(
    stage_repo: StageRepo, github_api: GitHubApiFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(stage_repo.clone)
    base = stage_repo.git("rev-parse", "main")

    result = runner.invoke(
        app,
        [
            "plan-recheck",
            "--repo",
            REPO,
            "--branch",
            "HEAD",
            "--base",
            base,
            "--issues",
            "issues.json",
            "--dry-run",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    assert "fetch" not in result.output
    assert f"/repos/{REPO}/issues" not in result.output
    assert f"diff --name-only {base}..HEAD" in result.output
    assert github_api.sent == []
