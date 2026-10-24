"""A review reads the code under review: the PR's own files, each file's own pages, every lockfile
(#515), and the PR's base at its merge base (#593)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.ai.review.pipeline import (
    ReviewPipelineOrchestrator,
    _lockfiles_beside,
    _match_static_findings_to_files,
)
from devops_cli.ai.review.runner import (
    _materialize_pr_head,
    _prepare_pr_content,
    _run_orchestrator_review,
)
from devops_cli.ai.review_schema import SavedFinding
from devops_cli.github.client import CommitRef, PullRequest, PullRequestFile
from devops_cli.github.session import get_github_session
from devops_cli.models.git import ChangedFile
from tests.support.fakes.github import (
    github_json,
    github_text,
    pull_request_file_payload,
    pull_request_payload,
    route_file,
    route_merge_base,
    route_pull_request,
)
from tests.support.paths import FIXTURES

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake

_MERGE_BASE = "merge789"
_HEAD_OF_158 = "ec18ca7bca5202d8e139a58b25757dc161255245"


def _pull() -> PullRequest:
    """A pull request from `fork/app` into `base/app`, whose base branch has moved on since."""
    return PullRequest(
        title="Change the app",
        head=CommitRef(sha="abc123", ref="feature", repository="fork/app"),
        base=CommitRef(sha="base456", ref="main", repository="base/app"),
    )


def _read_in(api: GitHubApiFake, repo: str) -> list[tuple[str, str]]:
    """The path and ref of each file of `repo` the fake was asked for, in order."""
    contents = f"/repos/{repo}/contents/"
    return [
        (request.url.path.removeprefix(contents), request.url.params["ref"])
        for request in api.sent
        if request.url.path.startswith(contents)
    ]


def test_a_pr_review_reads_the_pr_heads_files_and_conventions(
    tmp_path: Path, github_api: GitHubApiFake, pin_github_session: str
) -> None:
    """Verify changed files are written from head repo, and conventions are safely loaded from base (#658)."""
    route_file(github_api, "fork/app", "src/app.py", "abc123", "print('head version')\n")
    route_file(github_api, "base/app", "AGENTS.md", "base456", "# Conventions\n")
    route_file(github_api, "base/app", ".devops/review.md", "base456", "# Review rules\n")
    files = [
        PullRequestFile(filename=name, status=status, additions=1, changes=1)
        for name, status in (
            ("src/app.py", "modified"),
            ("old.py", "removed"),
            ("../escape.py", "added"),
        )
    ]

    written = _materialize_pr_head(
        get_github_session().client, "base/app", _pull(), tmp_path, files
    )

    assert (
        written,
        (tmp_path / "src/app.py").read_text(encoding="utf-8"),
        (tmp_path / ".devops/review.md").exists(),
        (tmp_path / "old.py").exists(),
        (tmp_path.parent / "escape.py").exists(),
        _read_in(github_api, "fork/app"),
        (".devops/review.md", "base456") in _read_in(github_api, "base/app"),
        {request.headers["authorization"] for request in github_api.sent},
    ) == (
        3,
        "print('head version')\n",
        True,
        False,
        False,
        [("src/app.py", "abc123")],
        True,
        {f"token {pin_github_session}"},
    )


def test_the_pr_command_reviews_against_the_pr_head(tmp_path: Path) -> None:
    """Verify the review's target directory holds the PR head's files, not the local checkout."""
    from typer.testing import CliRunner

    from devops_cli.main import app

    seen: dict[str, Any] = {}

    def prepare(number: int, repo: Any, head_dir: Path) -> Any:
        (head_dir / "app.py").write_text("head\n", encoding="utf-8")
        return (["page"], "PR #7", _pull(), "base/app", None)

    def run(*args: Any, **kwargs: Any) -> list[Any]:
        target = kwargs["target_dir"]
        seen["content"] = (target / "app.py").read_text(encoding="utf-8")
        seen["local"] = target.resolve() == Path.cwd().resolve()
        return []

    with (
        patch("devops_cli.commands.review._make_review_clients", return_value=MagicMock()),
        patch("devops_cli.commands.review._prepare_pr_content", side_effect=prepare),
        patch("devops_cli.commands.review._execute_review_workflow", side_effect=run),
    ):
        result = CliRunner().invoke(app, ["review", "pr", "7", "--repo", "base/app"])

    assert (result.exit_code, seen) == (0, {"content": "head\n", "local": False})


def test_a_pr_review_of_the_recorded_pull_request_reads_both_pages_of_files(
    tmp_path: Path, github_api: GitHubApiFake, pin_github_session: str
) -> None:
    """The recorded pull request lists its files on two pages, and its fork was deleted, so GitHub
    reports its head repository as null: the review has the title and both files, and reads the
    head's text from the base repository, at the head commit."""
    recorded = json.loads(
        (FIXTURES / "github" / "hello_world_pull_request.json").read_text(encoding="utf-8")
    )
    first, second = recorded["files_pages"]
    repo = "octocat/Hello-World"
    github_api.route(
        "GET",
        f"/repos/{repo}/pulls/158",
        github_json(recorded["pull_request"]),
        github_text("diff --git a/README.md b/README.md\n+x\n", media_type="text/plain"),
    )
    github_api.route(
        "GET",
        f"/repos/{repo}/pulls/158/files?per_page=100",
        github_json(first["body"], headers={"link": first["link"]}),
    )
    github_api.route(
        "GET",
        "/repositories/1296269/pulls/158/files?per_page=1&page=2",
        github_json(second["body"], headers={"link": second["link"]}),
    )
    route_file(github_api, repo, "README.md", _HEAD_OF_158, "**Hello World!**\n")

    _pages, title, pull, _repo, base_revision = _prepare_pr_content(158, repo, head_dir=tmp_path)

    assert base_revision is not None
    assert (
        title,
        pull.head.repository,
        base_revision.changes,
        (tmp_path / "README.md").read_text(encoding="utf-8"),
        [path for path, ref in _read_in(github_api, repo) if ref == _HEAD_OF_158],
        {request.headers["authorization"] for request in github_api.sent},
    ) == (
        "PR #158: Update and rename README to README.md. Also Added Bolding",
        None,
        (
            ChangedFile(change_type="deleted", path="README"),
            ChangedFile(change_type="added", path="README.md"),
        ),
        "**Hello World!**\n",
        ["README.md"],
        {f"token {pin_github_session}"},
    )


def test_a_pr_review_reads_the_base_at_the_merge_base_and_records_the_delta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, github_api: GitHubApiFake
) -> None:
    """Verify a PR review reads each modified or renamed Python file from the base repository at
    the merge base, a renamed one at its old path, and records the delta in the session (#593).

    `pull.base.sha` is the base branch's tip: read there, symbols added on the base since the
    branch point would count as removed by the PR.
    """
    monkeypatch.setenv("DEVOPS_CLI_DATA_ANALYSIS_DIR", str(tmp_path / "analysis"))
    route_pull_request(
        github_api,
        "base/app",
        7,
        pull_request_payload(),
        files=[
            pull_request_file_payload("mod.py", "modified"),
            pull_request_file_payload("new_name.py", "renamed", previous_filename="old_name.py"),
            pull_request_file_payload("added.py", "added"),
            pull_request_file_payload("gone.py", "removed"),
        ],
        diff="diff --git a/mod.py b/mod.py\n@@ -1,5 +1,2 @@\n-def legacy_helper():\n",
    )
    route_merge_base(github_api, "base/app", "base456", "abc123", _MERGE_BASE)
    for repo, path, ref, text in (
        ("fork/app", "mod.py", "abc123", "def keep():\n    return 1\n"),
        (
            "fork/app",
            "new_name.py",
            "abc123",
            "def moved():\n    return 2\n\n\ndef fresh():\n    return 3\n",
        ),
        ("fork/app", "added.py", "abc123", "def brand_new():\n    return 4\n"),
        (
            "base/app",
            "mod.py",
            _MERGE_BASE,
            "def legacy_helper():\n    return 0\n\n\ndef keep():\n    return 1\n",
        ),
        (
            "base/app",
            "old_name.py",
            _MERGE_BASE,
            "def moved():\n    return 2\n\n\ndef dropped():\n    return 5\n",
        ),
        (
            "base/app",
            "mod.py",
            "base456",
            "def main_only():\n    return 6\n\n\ndef keep():\n    return 1\n",
        ),
    ):
        route_file(github_api, repo, path, ref, text)
    head_dir = tmp_path / "head"
    head_dir.mkdir()

    *_, base_revision = _prepare_pr_content(7, "base/app", head_dir=head_dir)
    orchestrator = ReviewPipelineOrchestrator(
        session_id="pr-7",
        llm_client=MagicMock(),
        session_dir=tmp_path / "session",
        concurrency=1,
        target_dir=head_dir,
    )
    metadata = orchestrator.run_pre_analysis_refresh(
        files=["mod.py", "new_name.py", "added.py"],
        target_type="pr",
        target_ref="7",
        base_revision=base_revision,
    )

    source_base_reads = sorted(
        (path, ref) for path, ref in _read_in(github_api, "base/app") if path.endswith(".py")
    )
    deltas = {
        path: (m.symbols_added, m.symbols_removed, m.symbols_retained)
        for path, m in metadata.items()
        if path.endswith(".py")
    }
    compared = [r for r in github_api.requested if "/compare/" in r]
    assert (compared, source_base_reads, deltas) == (
        ["GET https://api.github.com/repos/base/app/compare/base456...abc123?per_page=1"],
        [("mod.py", _MERGE_BASE), ("old_name.py", _MERGE_BASE)],
        {
            "mod.py": ([], ["legacy_helper"], ["keep"]),
            "new_name.py": (["fresh"], ["dropped"], ["moved"]),
            "added.py": (["brand_new"], [], []),
        },
    )


def test_a_pr_review_reads_the_merge_base_from_the_base_repository_the_pull_request_names(
    tmp_path: Path, github_api: GitHubApiFake
) -> None:
    """GitHub serves a pull request under the old name of a renamed repository, and reports the
    base repository by its full name: the merge base and the base files are read there, not under
    the name the review was asked for."""
    route_pull_request(
        github_api,
        "old/app",
        7,
        pull_request_payload(),
        files=[pull_request_file_payload("mod.py")],
        diff="diff --git a/mod.py b/mod.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n",
    )
    route_merge_base(github_api, "base/app", "base456", "abc123", _MERGE_BASE)
    route_file(github_api, "fork/app", "mod.py", "abc123", "x = 2\n")
    route_file(github_api, "base/app", "mod.py", _MERGE_BASE, "x = 1\n")

    *_, base_revision = _prepare_pr_content(7, "old/app", head_dir=tmp_path)

    assert base_revision is not None
    assert (
        base_revision.read("mod.py"),
        [request for request in github_api.requested if "/compare/" in request],
        _read_in(github_api, "old/app"),
    ) == (
        "x = 1\n",
        ["GET https://api.github.com/repos/base/app/compare/base456...abc123?per_page=1"],
        [],
    )


def _route_a_modified_python_file(api: GitHubApiFake) -> None:
    """Serve pull request 7 of base/app, which modifies mod.py, with its head text and merge base."""
    route_pull_request(
        api,
        "base/app",
        7,
        pull_request_payload(),
        files=[pull_request_file_payload("mod.py")],
        diff="diff --git a/mod.py b/mod.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n",
    )
    route_merge_base(api, "base/app", "base456", "abc123", _MERGE_BASE)
    route_file(api, "fork/app", "mod.py", "abc123", "x = 2\n")


def test_a_pr_review_ends_with_the_github_error_when_the_pull_request_cannot_be_read(
    cli: Callable[..., Any], github_api: GitHubApiFake
) -> None:
    """A 500 that outlasts the retries ends the command with the session's message and status 1,
    and prints no traceback."""
    github_api.route(
        "GET", "/repos/base/app/pulls/7", github_json({"message": "Server Error"}, status=500)
    )

    result = cli("review", "pr", "7", "--repo", "base/app", "--pre-analysis-only")

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert "HTTP 500" in result.output
    assert "Traceback" not in result.output


@pytest.mark.parametrize("unreadable", ["mod.py", ".devops/review.toml"])
def test_a_pr_review_ends_with_the_github_error_when_a_file_of_the_base_cannot_be_read(
    cli: Callable[..., Any], github_api: GitHubApiFake, unreadable: str
) -> None:
    """A failed read of a file at the merge base is no absent file: the modified Python file
    would have no symbol delta, and the review configuration would be the default one. The
    command ends with the session's message and status 1, and prints no traceback."""
    _route_a_modified_python_file(github_api)
    github_api.route(
        "GET",
        f"/repos/base/app/contents/{unreadable}?ref={_MERGE_BASE}",
        github_json({"message": "Server Error"}, status=500),
    )

    result = cli("review", "pr", "7", "--repo", "base/app", "--pre-analysis-only")

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert f"contents/{unreadable}?ref={_MERGE_BASE} (HTTP 500)" in result.output
    assert "Traceback" not in result.output


def test_each_file_is_reviewed_with_its_own_pages_only() -> None:
    """Verify `a.py` is not given the pages of `data.py`, whose name contains it."""
    orchestrator = MagicMock()
    orchestrator.init_per_file_payloads.return_value = []
    orchestrator.generate_consolidated_report.return_value = ({}, "report")
    pages = ["### File: data.py\n```python\nx = 1\n```", "### File: a.py\n```python\ny = 2\n```"]

    _run_orchestrator_review(orchestrator, ["a.py", "data.py"], {}, pages)

    diff_map = orchestrator.init_per_file_payloads.call_args.kwargs["diff_text_by_file"]
    assert (diff_map["a.py"], diff_map["data.py"]) == (pages[1], pages[0])


def test_lockfiles_beside_reviewed_files_reach_the_scanners(tmp_path: Path) -> None:
    """Verify a lockfile left out of the persona review is still scanned, and its finding kept."""
    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    (tmp_path / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
    finding = SavedFinding(
        location="svc/uv.lock:12", title="[trivy] CVE-2024-0001 in requests", description="d"
    )

    lockfiles = _lockfiles_beside([tmp_path / "app.py", tmp_path / "pyproject.toml"])
    attached = _match_static_findings_to_files([finding], ["svc/app.py", "svc/pyproject.toml"])

    assert ([p.name for p in lockfiles], list(attached)) == (["uv.lock"], ["svc/pyproject.toml"])
