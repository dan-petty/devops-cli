"""A review reads the code under review: the PR's own files, each file's own pages, every lockfile
(#515), and the PR's base at the merge base of its base branch (#593, #5346)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

from devops_cli.ai.review.pipeline import (
    ReviewPipelineOrchestrator,
    _evaluate_session_complexity_deltas,
    _lockfiles_beside,
    _populate_gomod_for_dir,
    _write_base_revision_files,
    match_static_findings_to_files,
    write_base_revision_lockfiles,
)
from devops_cli.ai.review.runner import (
    _materialize_pr_head,
    _prepare_pr_content,
    run_orchestrator_review,
)
from devops_cli.ai.review_schema import SavedFinding
from devops_cli.config.constants import CONST_GITHUB_COMPARE_FILES_LIMIT
from devops_cli.github.client import CommitRef, CompareFiles, PullRequest, PullRequestFile
from devops_cli.github.session import get_github_session
from devops_cli.models.git import ChangedFile
from devops_cli.review.diff import diff_file_names
from tests.support.fakes.github import (
    github_json,
    pull_request_file_payload,
    pull_request_payload,
    route_compare_diff,
    route_compare_files,
    route_file,
    route_pull_request,
    route_pull_request_changes,
)
from tests.support.paths import FIXTURES

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.model import ModelFake

_MERGE_BASE = "merge789"
_HEAD_OF_158 = "ec18ca7bca5202d8e139a58b25757dc161255245"


def _pull() -> PullRequest:
    """A pull request from `fork/app` into `base/app`, whose base branch has moved on since."""
    return PullRequest(
        title="Change the app",
        head=CommitRef(sha="abc123", ref="feature", repository="fork/app"),
        base=CommitRef(sha="base456", ref="main", repository="base/app"),
    )


def _compared(*files: PullRequestFile) -> CompareFiles:
    """The compare of the base branch of `_pull()` and its head: `files`, from `_MERGE_BASE`."""
    return CompareFiles(files=list(files), truncated=False, merge_base=_MERGE_BASE)


def _read_in(api: GitHubApiFake, repo: str) -> list[tuple[str, str]]:
    """The path and ref of each file of `repo` the fake was asked for, in order."""
    contents = f"/repos/{repo}/contents/"
    return [
        (request.url.path.removeprefix(contents), request.url.params["ref"])
        for request in api.sent
        if request.url.path.startswith(contents)
    ]


def test_a_pr_checkout_carries_no_review_guards_file_from_the_base(
    tmp_path: Path, github_api: GitHubApiFake, pin_github_session: str
) -> None:
    """Verify a pull request checkout takes `AGENTS.md` from the base and no `.devops/review.md` (#1916)."""
    route_file(github_api, "base/app", "AGENTS.md", _MERGE_BASE, "# Conventions\n")
    route_file(github_api, "base/app", ".devops/review.md", _MERGE_BASE, "# Review rules\n")

    _materialize_pr_head(get_github_session().client, "base/app", _pull(), tmp_path, _compared())

    assert (
        (tmp_path / "AGENTS.md").read_text(encoding="utf-8"),
        (tmp_path / ".devops/review.md").exists(),
        (".devops/review.md", _MERGE_BASE) in _read_in(github_api, "base/app"),
    ) == ("# Conventions\n", False, False)


def test_a_pr_review_reads_the_pr_heads_files_and_conventions(
    tmp_path: Path, github_api: GitHubApiFake, pin_github_session: str
) -> None:
    """Verify changed files are written from head repo, and conventions are safely loaded from
    the base at the merge base (#658, #5346)."""
    route_file(github_api, "fork/app", "src/app.py", "abc123", "print('head version')\n")
    route_file(github_api, "base/app", "AGENTS.md", _MERGE_BASE, "# Conventions\n")
    files = [
        PullRequestFile(filename=name, status=status, additions=1, changes=1)
        for name, status in (
            ("src/app.py", "modified"),
            ("old.py", "removed"),
            ("../escape.py", "added"),
        )
    ]

    written = _materialize_pr_head(
        get_github_session().client, "base/app", _pull(), tmp_path, _compared(*files)
    )

    assert (
        written,
        (tmp_path / "src/app.py").read_text(encoding="utf-8"),
        (tmp_path / "AGENTS.md").read_text(encoding="utf-8"),
        (tmp_path / "old.py").exists(),
        (tmp_path.parent / "escape.py").exists(),
        _read_in(github_api, "fork/app"),
        {request.headers["authorization"] for request in github_api.sent},
    ) == (
        2,
        "print('head version')\n",
        "# Conventions\n",
        False,
        False,
        [("src/app.py", "abc123")],
        {f"token {pin_github_session}"},
    )


def test_the_pr_command_reviews_against_the_pr_head(
    cli: Callable[..., Any],
    github_api: GitHubApiFake,
    pin_github_session: str,
    model_fake: ModelFake,
    scanner_fake: Any,
) -> None:
    """Verify the review's target directory holds the PR head's files, not the local checkout."""
    from tests.support.fakes.model import LLMResponse

    pull = pull_request_payload(
        title="Change the app",
        head_sha="abc123",
        base_sha="base456",
        head_repo="fork/app",
        base_repo="base/app",
    )
    route_pull_request(github_api, "base/app", 7, pull)
    route_pull_request_changes(
        github_api,
        pull,
        pull_request_file_payload("app.py", "added"),
        merge_base=_MERGE_BASE,
        diff="diff --git a/app.py b/app.py\n--- /dev/null\n+++ b/app.py\n@@ -0,0 +1 @@\n+head\n",
    )
    route_file(github_api, "fork/app", "app.py", "abc123", "head\n")
    route_file(github_api, "base/app", "AGENTS.md", _MERGE_BASE, "# Conventions\n")

    model_fake.answer(LLMResponse(content="[]", model="fake-model"))

    result = cli("review", "pr", "7", "--repo", "base/app", "--no-group-analysis")

    assert result.exit_code == 0
    assert not (Path.cwd() / "app.py").exists()
    assert result.exit_code == 0
    assert not (Path.cwd() / "app.py").exists()
    assert any("/fork/app/contents/app.py" in r.url.path for r in github_api.sent)
    assert "Files Reviewed       1" in result.stdout


def test_a_pr_review_of_the_recorded_pull_request_reads_the_compare_of_its_base_branch(
    tmp_path: Path, github_api: GitHubApiFake, pin_github_session: str
) -> None:
    """The recorded compare of the base branch and the head commit lists both files of the pull
    request, whose fork was deleted, so GitHub reports its head repository as null: the review has
    the title and both files, and reads the head's text from the base repository, at the head
    commit."""
    recorded = json.loads(
        (FIXTURES / "github" / "hello_world_pull_request.json").read_text(encoding="utf-8")
    )
    comparison = recorded["branch_comparison"]
    repo = "octocat/Hello-World"
    github_api.route("GET", f"/repos/{repo}/pulls/158", github_json(recorded["pull_request"]))
    github_api.route(
        "GET",
        f"/repos/{repo}/compare/master...{_HEAD_OF_158}?per_page=1",
        github_json(comparison),
    )
    merge_base = comparison["merge_base_commit"]["sha"]
    route_compare_diff(
        github_api, repo, merge_base, _HEAD_OF_158, "diff --git a/README.md b/README.md\n+x\n"
    )
    route_file(github_api, repo, "README.md", _HEAD_OF_158, "**Hello World!**\n")

    _pages, title, pull, _repo, base_revision = _prepare_pr_content(158, repo, head_dir=tmp_path)

    assert base_revision is not None
    assert (
        title,
        pull.head.repository,
        base_revision.changes,
        base_revision.revision,
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
        merge_base,
        "**Hello World!**\n",
        ["README.md"],
        {f"token {pin_github_session}"},
    )


def test_a_pr_review_reads_the_changes_at_the_merge_base_of_its_base_branch(
    tmp_path: Path, github_api: GitHubApiFake
) -> None:
    """A merge of the base branch into the pull request moved its merge base, and GitHub kept
    the payload's `base.sha` and the file list of the pulls endpoints at the old base (#5346).
    The review reads the files and the diff of the compare of the base branch and the head
    commit, and the base text and the conventions at the merge base of that compare. No request
    names `base.sha` or the pulls files path, and the diff of the pulls endpoint is not read."""
    pull = pull_request_payload(base_sha="stale456")
    route_pull_request(
        github_api,
        "base/app",
        7,
        pull,
        files=[pull_request_file_payload("mod.py"), pull_request_file_payload("main_only.py")],
        diff="diff --git a/main_only.py b/main_only.py\n@@ -1 +1 @@\n-y = 1\n+y = 2\n",
    )
    route_pull_request_changes(
        github_api,
        pull,
        pull_request_file_payload("mod.py"),
        merge_base=_MERGE_BASE,
        diff="diff --git a/mod.py b/mod.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n",
    )
    route_file(github_api, "fork/app", "mod.py", "abc123", "x = 2\n")
    for ref, mod, conventions in (
        (_MERGE_BASE, "x = 1\n", "# Conventions at the merge base\n"),
        ("stale456", "x = 0\n", "# Conventions at the stale base\n"),
    ):
        route_file(github_api, "base/app", "mod.py", ref, mod)
        route_file(github_api, "base/app", "AGENTS.md", ref, conventions)

    pages, _title, _pull, _repo, base_revision = _prepare_pr_content(
        7, "base/app", head_dir=tmp_path
    )

    assert base_revision is not None
    assert (
        [name for page in pages for name in diff_file_names(page)],
        base_revision.changes,
        base_revision.read("mod.py"),
        base_revision.revision,
        (tmp_path / "AGENTS.md").read_text(encoding="utf-8"),
        (tmp_path / "main_only.py").exists(),
        [request for request in github_api.requested if "/contents/" not in request],
        {ref for _path, ref in _read_in(github_api, "base/app")},
    ) == (
        ["mod.py"],
        (ChangedFile(change_type="modified", path="mod.py"),),
        "x = 1\n",
        _MERGE_BASE,
        "# Conventions at the merge base\n",
        False,
        [
            "GET https://api.github.com/repos/base/app/pulls/7",
            "GET https://api.github.com/repos/base/app/compare/main...abc123?per_page=1",
            f"GET https://api.github.com/repos/base/app/compare/{_MERGE_BASE}...abc123",
        ],
        {_MERGE_BASE},
    )


def test_a_pr_review_refuses_a_comparison_at_the_file_limit(
    cli: Callable[..., Any], github_api: GitHubApiFake
) -> None:
    """GitHub lists at most `CONST_GITHUB_COMPARE_FILES_LIMIT` files of one comparison. A list at
    that limit can miss files of the pull request, and the review would miss their changes: the
    command ends with status 1 and a message that names the limit, and reads no diff."""
    route_pull_request(github_api, "base/app", 7, pull_request_payload())
    route_compare_files(
        github_api,
        "base/app",
        "main",
        "abc123",
        *[
            pull_request_file_payload(f"src/{number}.py")
            for number in range(CONST_GITHUB_COMPARE_FILES_LIMIT)
        ],
        merge_base=_MERGE_BASE,
    )

    result = cli("review", "pr", "7", "--repo", "base/app", "--pre-analysis-only")

    output = " ".join(result.output.split())
    assert (
        result.exit_code,
        f"{CONST_GITHUB_COMPARE_FILES_LIMIT} files" in output,
        "devops review branch" in output,
        [request for request in github_api.requested if "/compare/" in request],
    ) == (
        1,
        True,
        True,
        ["GET https://api.github.com/repos/base/app/compare/main...abc123?per_page=1"],
    )


def test_a_pr_review_reads_the_base_at_the_merge_base_and_records_the_delta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, github_api: GitHubApiFake
) -> None:
    """Verify a PR review reads each modified or renamed Python file from the base repository at
    the merge base, a renamed one at its old path, and records the delta in the session (#593).

    `pull.base.sha` is a tip of the base branch that GitHub recorded earlier: read there, symbols
    added on the base since the branch point would count as removed by the PR.
    """
    monkeypatch.setenv("DEVOPS_CLI_DATA_ANALYSIS_DIR", str(tmp_path / "analysis"))
    pull = pull_request_payload()
    route_pull_request(github_api, "base/app", 7, pull)
    route_pull_request_changes(
        github_api,
        pull,
        pull_request_file_payload("mod.py", "modified"),
        pull_request_file_payload("new_name.py", "renamed", previous_filename="old_name.py"),
        pull_request_file_payload("added.py", "added"),
        pull_request_file_payload("gone.py", "removed"),
        merge_base=_MERGE_BASE,
        diff="diff --git a/mod.py b/mod.py\n@@ -1,5 +1,2 @@\n-def legacy_helper():\n",
    )
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
        [
            "GET https://api.github.com/repos/base/app/compare/main...abc123?per_page=1",
            f"GET https://api.github.com/repos/base/app/compare/{_MERGE_BASE}...abc123",
        ],
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
    base repository by its full name: the comparison and the base files are read there, not under
    the name the review was asked for."""
    pull = pull_request_payload()
    route_pull_request(github_api, "old/app", 7, pull)
    route_pull_request_changes(
        github_api,
        pull,
        pull_request_file_payload("mod.py"),
        merge_base=_MERGE_BASE,
        diff="diff --git a/mod.py b/mod.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n",
    )
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
        [
            "GET https://api.github.com/repos/base/app/compare/main...abc123?per_page=1",
            f"GET https://api.github.com/repos/base/app/compare/{_MERGE_BASE}...abc123",
        ],
        [],
    )


def _route_a_modified_python_file(api: GitHubApiFake) -> None:
    """Serve pull request 7 of base/app, which modifies mod.py, with its head text and merge base."""
    pull = pull_request_payload()
    route_pull_request(api, "base/app", 7, pull)
    route_pull_request_changes(
        api,
        pull,
        pull_request_file_payload("mod.py"),
        merge_base=_MERGE_BASE,
        diff="diff --git a/mod.py b/mod.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n",
    )
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

    run_orchestrator_review(orchestrator, ["a.py", "data.py"], {}, pages)

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
    attached = match_static_findings_to_files([finding], ["svc/app.py", "svc/pyproject.toml"])

    assert ([p.name for p in lockfiles], list(attached)) == (["uv.lock"], ["svc/pyproject.toml"])


def test_a_base_revision_file_read_failure_records_a_coverage_gap(
    tmp_path: Path, github_api: GitHubApiFake
) -> None:
    """A failed read of a base revision file records a coverage gap with the reason (#1907)."""
    _route_a_modified_python_file(github_api)
    github_api.route(
        "GET",
        f"/repos/base/app/contents/mod.py?ref={_MERGE_BASE}",
        github_json({"message": "Server Error"}, status=500),
    )
    *_, base_revision = _prepare_pr_content(7, "base/app", head_dir=tmp_path)
    assert base_revision is not None

    gaps: dict[str, str] = {}
    written = _write_base_revision_files(
        base_revision, tmp_path / "base", {"mod.py"}, coverage_gaps=gaps
    )
    assert (
        written,
        "mod.py" in gaps,
        "Base revision:" in gaps.get("mod.py", ""),
        "HTTP 500" in gaps.get("mod.py", ""),
    ) == (
        [],
        True,
        True,
        True,
    )

    complexity_gaps: dict[str, str] = {}
    (tmp_path / "mod.py").write_text("x = 2\n", encoding="utf-8")
    _evaluate_session_complexity_deltas(
        [tmp_path / "mod.py"], tmp_path, base_revision, 10, None, coverage_gaps=complexity_gaps
    )
    assert (
        "mod.py" in complexity_gaps,
        "Base revision:" in complexity_gaps.get("mod.py", ""),
        "HTTP 500" in complexity_gaps.get("mod.py", ""),
    ) == (True, True, True)

    lockfile_gaps: dict[str, str] = {}
    github_api.route(
        "GET",
        f"/repos/base/app/contents/uv.lock?ref={_MERGE_BASE}",
        github_json({"message": "Server Error"}, status=500),
    )
    write_base_revision_lockfiles(
        base_revision, tmp_path / "base", ["mod.py"], coverage_gaps=lockfile_gaps
    )
    assert (
        "uv.lock" in lockfile_gaps,
        "Base revision:" in lockfile_gaps.get("uv.lock", ""),
        "HTTP 500" in lockfile_gaps.get("uv.lock", ""),
    ) == (True, True, True)

    gomod_gaps: dict[str, str] = {}
    github_api.route(
        "GET",
        f"/repos/base/app/contents/go.mod?ref={_MERGE_BASE}",
        github_json({"message": "Server Error"}, status=500),
    )
    _populate_gomod_for_dir(
        base_revision, tmp_path / "base", Path("pkg"), [], [], coverage_gaps=gomod_gaps
    )
    assert (
        "go.mod" in gomod_gaps,
        "Base revision:" in gomod_gaps.get("go.mod", ""),
        "HTTP 500" in gomod_gaps.get("go.mod", ""),
    ) == (True, True, True)
