"""Unit tests for AI review runner, prompt construction, and session persistence."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from devops_cli.ai.personas import PERSONAS, Persona
from devops_cli.ai.review.history import review_subject
from devops_cli.ai.review.runner import (
    _collect_file_blocks,
    _git_repo_root,
    _is_allowed_review_boundary,
    _make_review_clients,
    _prepare_branch_content,
    _prepare_path_content,
    _prepare_pr_content,
)
from devops_cli.ai.review_schema import (
    Finding,
    ReviewResult,
    ReviewSessionPayload,
    SavedFinding,
)
from devops_cli.commands.review import app as review_app
from devops_cli.config.settings import Settings
from devops_cli.core.gitignore import reset_indexes
from devops_cli.core.repo import is_ignored_by_git
from devops_cli.models.vulnerability import DependencySpec, NetworkReference
from devops_cli.output import (
    render_review_raw,
    render_review_result,
)
from devops_cli.review.session import ReviewSessionStore
from tests.support.fakes.github import pull_request_payload, route_pull_request
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.paths import REPO_ROOT

if TYPE_CHECKING:
    from tests.support.fakes.git import GitFake
    from tests.support.fakes.github import GitHubApiFake

pytestmark = pytest.mark.usefixtures("keyring_store")


def test_rendering_helpers(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify rendering of structured review results and raw markdown."""
    persona_def = PERSONAS[Persona.DEVSECOPS]
    finding = Finding(
        severity="HIGH",
        title="Test Vuln",
        description="Desc",
        location="src/main.py:10",
        fix="Fix",
        status="VERIFIED",
        verified=True,
    )
    dep = DependencySpec(
        name="requests",
        version_range="2.25.0",
        ecosystem="PyPI",
        severity="HIGH",
        security_status="VULNERABLE",
        source_file="pyproject.toml",
        line_number=10,
    )
    net = NetworkReference(
        target="1.1.1.1",
        reference_type="ipv4",
        is_local=False,
        security_status="Clean",
        source_file="src/net.py",
        line_number=5,
    )
    res = ReviewResult(
        persona=Persona.DEVSECOPS,
        recommendation="REQUEST CHANGES",
        findings=[finding],
        external_dependencies=[dep],
        network_references=[net],
        summary="Summary of issues",
        raw_markdown="# Security Review",
    )
    render_review_result(persona_def, res)
    render_review_raw(persona_def, "## Raw review text")
    captured = capsys.readouterr()
    assert "Test Vuln" in captured.out
    assert "Raw review text" in captured.out


def test_runner_file_and_repo_helpers(tmp_path: Path, git_fake: GitFake) -> None:
    """Verify runner repository traversal, git boundary, and gitignore evaluation."""
    git_fake.answer(
        lambda call: bool(call.argv and "ls-files" in call.argv),
        ProcessAnswer(returncode=0, stdout="src/app.py\0"),
    )
    st = Settings()
    st.repos.base_dir = tmp_path
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / ".git").mkdir()
    (repo_dir / "src").mkdir()
    sample_file = repo_dir / "src" / "app.py"
    sample_file.write_text("print('hello')\n")

    assert (
        _git_repo_root(sample_file),
        _is_allowed_review_boundary(sample_file, st, tmp_path),
        is_ignored_by_git(repo_dir, sample_file),
    ) == (repo_dir, True, False)

    (repo_dir / ".gitignore").write_text("*.py\n")
    # Compiled ignore files are revalidated on an interval rather than stat-ed per call,
    # so a rule written this instant is visible once the cached evaluator is reset.
    reset_indexes()
    assert is_ignored_by_git(repo_dir, sample_file) is True
    (repo_dir / ".gitignore").unlink()

    blocks = _collect_file_blocks(repo_dir / "src", "*.py")
    assert len(blocks) >= 1


def test_prepare_content_helpers(
    tmp_path: Path, github_api: GitHubApiFake, process_fake: ProcessFake
) -> None:
    """Verify content preparation for paths, branches, and PRs."""
    test_file = REPO_ROOT / "src/devops_cli/main.py"

    pages, title, routed = _prepare_path_content(test_file, "*", working_directory=REPO_ROOT)
    assert (len(pages) >= 1, "main.py" in title, routed) == (True, True, [])

    process_fake.answer(
        "git diff",
        ProcessAnswer(
            returncode=0,
            stdout="diff --git a/test.py b/test.py\n+def foo(): return 42\n",
        ),
    )

    with (
        patch("devops_cli.git.operations.resolve_merge_base", return_value="base-sha"),
        patch("devops_cli.git.operations.list_changed_files", return_value=[]),
    ):
        b_pages, b_title, b_target, _ = _prepare_branch_content(
            "feat/test", "main", REPO_ROOT, working_directory=REPO_ROOT
        )
        assert (len(b_pages) >= 1, "feat/test" in b_title, b_target) == (True, True, "feat/test")

    route_pull_request(
        github_api,
        "owner/repo",
        123,
        pull_request_payload(title="Mock PR Title"),
        diff="diff --git a/test.py b/test.py\n+content\n",
    )
    pr_pages, pr_title, pull, repo, pr_base = _prepare_pr_content(123, repo_arg="owner/repo")
    assert (len(pr_pages) >= 1, pr_title, pull.title, repo, pr_base is None) == (
        True,
        "PR #123: Mock PR Title",
        "Mock PR Title",
        "owner/repo",
        True,
    )


def test_a_pr_review_with_no_repo_names_the_origin_of_the_checkout_it_gets(
    tmp_path: Path, github_api: GitHubApiFake, process_fake: ProcessFake
) -> None:
    """With no `--repo`, the PR review reads the pull request of the origin of the checkout that
    the command gives, not of the directory that the process runs in (#2127)."""
    checkout = tmp_path / "checkout"
    (checkout / ".git").mkdir(parents=True)
    process_fake.answer(
        "git remote get-url origin",
        ProcessAnswer(stdout="git@github.com:example-org/app.git\n"),
    )
    route_pull_request(
        github_api,
        "example-org/app",
        7,
        pull_request_payload(title="Origin PR"),
        diff="diff --git a/app.py b/app.py\n+content\n",
    )
    *_, repo, _base = _prepare_pr_content(7, checkout=checkout)
    assert (repo, [call.cwd for call in process_fake.calls]) == (
        "example-org/app",
        [checkout.resolve()],
    )


def test_review_runner_extended_branches(review_store: type[ReviewSessionStore]) -> None:
    """Verify session lookup and markdown formatting."""
    from devops_cli.ai.review.runner import (
        _find_session_dir,
        _review_to_markdown,
    )

    # 1. Review to markdown with unverified and mitigated findings
    finding_mit = Finding(
        severity="HIGH",
        title="Mitigated Vuln",
        description="Desc",
        location="src/main.py:10",
        mitigated=True,
    )
    finding_unver = Finding(
        severity="LOW",
        title="Unverified Vuln",
        description="Desc",
        location="src/main.py:20",
        verified=False,
    )
    res_mit = ReviewResult(
        persona=Persona.DEVSECOPS,
        findings=[finding_mit, finding_unver],
        summary="Review complete",
    )
    md = _review_to_markdown(res_mit)
    assert ("*(mitigated)*" in md, "*(unverified)*" in md) == (True, True)

    # 2. Session directory lookup
    s1 = review_store.root() / "20260826-120000-session1"
    s1.mkdir()
    (s1 / "findings.json").write_text("{}", encoding="utf-8")
    found = _find_session_dir("session1")
    assert found == s1


def test_review_cli_commands(tmp_path: Path, review_store: type[ReviewSessionStore]) -> None:
    """Verify review findings, verify, stats, and export-feedback commands."""
    runner = CliRunner()
    session_dir = review_store.root() / "20260826-000000-sample-session"
    session_dir.mkdir()

    findings = [
        SavedFinding(
            id=1,
            title="Insecure Port Binding",
            severity="HIGH",
            location="src/app.py:10",
            status="UNVERIFIED",
            producer="devsecops",
            recommendation="REQUEST CHANGES",
            confidence_score=0.90,
        ),
        SavedFinding(
            id=2,
            title="Missing Docstring",
            severity="LOW",
            location="src/app.py:20",
            status="VERIFIED",
            verified=True,
            verified_by="criteria",
            producer="qa",
            recommendation="COMMENT",
            confidence_score=0.80,
        ),
    ]
    payload = ReviewSessionPayload(
        generated_at="2026-08-26T00:00:00",
        subject=review_subject("path", "src/", []),
        findings=findings,
    )
    (session_dir / "findings.json").write_text(payload.model_dump_json(indent=2), encoding="utf-8")

    # 1. Findings table
    res_find = runner.invoke(review_app, ["findings", "--session", "sample-session"])
    assert res_find.exit_code == 0
    assert "Insecure Port Binding" in res_find.output

    # 2. Findings filter
    res_find_unver = runner.invoke(
        review_app, ["findings", "--session", "sample-session", "--unverified"]
    )
    assert res_find_unver.exit_code == 0

    # 3. Verify finding by index
    res_ver_idx = runner.invoke(
        review_app,
        [
            "verify",
            "sample-session",
            "--index",
            "1",
            "--status",
            "INVALIDATED",
            "--reason",
            "False positive",
        ],
    )
    assert res_ver_idx.exit_code == 0
    assert "Updated finding #1" in res_ver_idx.output

    # 4. Verify finding by title
    res_ver_title = runner.invoke(
        review_app,
        ["verify", "sample-session", "--title", "Missing Docstring", "--status", "MITIGATED"],
    )
    assert res_ver_title.exit_code == 0

    # 5. Review stats
    res_stats = runner.invoke(review_app, ["stats"])
    assert res_stats.exit_code == 0
    assert "devsecops" in res_stats.output

    # 6. Export feedback
    res_exp = runner.invoke(
        review_app, ["export-feedback", "--output", str(tmp_path / "feedback.json")]
    )
    assert res_exp.exit_code == 0


def test_review_findings_without_a_session_reads_the_latest_published_one(
    cli: Callable[..., Any], review_store: type[ReviewSessionStore]
) -> None:
    """Verify the default session is the newest one whose review finished, not a review still
    running, nor the one modified last (#771)."""
    for name, title, published in (
        ("20261001-120000", "Older review", True),
        ("20261002-120000", "Newest finished review", True),
        ("20261003-120000", "Review still running", False),
    ):
        session = review_store.session(name)
        finding = SavedFinding(
            title=title, severity="HIGH", location="src/app.py:10", description="d"
        )
        session.write_findings(ReviewSessionPayload(findings=[finding]))
        if published:
            session.publish()
    os.utime(review_store.root() / "20261001-120000", (4_000_000_000, 4_000_000_000))

    result = cli("review", "findings")

    assert (
        result.exit_code,
        "Newest finished review" in result.output,
        "Review still running" in result.output,
        "Older review" in result.output,
    ) == (0, True, False, False)


def test_detect_base_branch(tmp_path: Path, process_fake: ProcessFake) -> None:
    """Verify base branch detection and fallback handling."""
    from devops_cli.ai.review.runner import _detect_base_branch

    process_fake.answer(
        lambda call: "origin/feat/1-example" in call.argv,
        ProcessAnswer(returncode=0, stdout="origin/feat/1-example\n"),
    )
    b = _detect_base_branch(tmp_path, preferred_base="feat/1-example")
    assert "feat/1-example" in b

    process_fake.answer(
        lambda call: True,
        ProcessAnswer(returncode=1, stdout="", stderr="err"),
    )
    b_fallback = _detect_base_branch(tmp_path)
    assert b_fallback in ("main", "master")


def test_is_allowed_review_boundary() -> None:
    """Verify review path boundary isolation and forbidden system path rejections."""
    from devops_cli.ai.review.runner import _is_allowed_review_boundary
    from devops_cli.config.settings import Settings

    st = Settings()
    assert (
        _is_allowed_review_boundary(REPO_ROOT / "src/app.py", st, REPO_ROOT),
        _is_allowed_review_boundary(Path("/etc/shadow"), st, REPO_ROOT),
        _is_allowed_review_boundary(Path("/etc/passwd"), st, REPO_ROOT),
    ) == (True, False, False)


def test_review_to_markdown() -> None:
    """Verify review markdown generation formatting."""
    from devops_cli.ai.review.runner import _review_to_markdown

    f = Finding(
        severity="MEDIUM",
        title="Tight Coupling",
        description="Service couples DB and API layers",
        location="src/service.py:15-30",
        fix="Extract repository layer",
    )

    res = ReviewResult(
        persona=Persona.ARCHITECT,
        recommendation="COMMENT",
        findings=[f],
        summary="Architecture is mostly sound.",
    )
    md = _review_to_markdown(res)
    assert (
        "Tight Coupling" in md,
        "## Model Notes (Not Verified)" in md,
        "Architecture is mostly sound" in md,
    ) == (True, True, True)


def test_make_review_clients() -> None:
    """Verify creation of analysis review client."""
    from devops_cli.ai.client import LLMClient
    from devops_cli.config.settings import Settings

    st = Settings()
    st.ai.ollama_urls = ["http://localhost:11434"]
    clients = _make_review_clients(st)
    assert isinstance(clients.analysis, LLMClient)
    assert clients.analysis._config.task_name == "analysis"


def test_review_clients_wait_a_configured_task_timeout() -> None:
    """Verify a configured analysis timeout replaces the review default."""
    from devops_cli.config.defaults import DEFAULT_REVIEW_TIMEOUT_SECONDS
    from devops_cli.config.settings import AITaskOverride, Settings

    st = Settings()
    st.ai.ollama_urls = ["http://localhost:11434"]
    st.ai.tasks.analysis = AITaskOverride(timeout=30.0)
    configured = _make_review_clients(st)
    def_st = Settings()
    def_st.ai.ollama_urls = ["http://localhost:11434"]
    defaults = _make_review_clients(def_st)

    assert (
        configured.analysis._request_timeout().read,
        defaults.analysis._request_timeout().read,
    ) == (30.0, DEFAULT_REVIEW_TIMEOUT_SECONDS)


def test_get_current_git_branch(process_fake: ProcessFake) -> None:
    """Verify active branch name detection and detached HEAD handling."""
    from devops_cli.ai.review.runner import _get_current_git_branch

    # Attached branch
    process_fake.answer(lambda call: True, ProcessAnswer(returncode=0, stdout="feat/20-example\n"))
    assert _get_current_git_branch(Path(".")) == "feat/20-example"

    # Detached HEAD
    process_fake.answer(lambda call: True, ProcessAnswer(returncode=0, stdout="HEAD\n"))
    assert _get_current_git_branch(Path(".")) == ""

    # Failure
    process_fake.answer(lambda call: True, ProcessAnswer(returncode=1, stdout="", stderr="fatal"))
    assert _get_current_git_branch(Path(".")) == ""


def test_has_uncommitted_working_tree_changes(process_fake: ProcessFake) -> None:
    """Verify detection of staged and unstaged working tree changes."""
    from devops_cli.ai.review.runner import _has_uncommitted_working_tree_changes

    process_fake.answer(
        lambda call: True, ProcessAnswer(returncode=0, stdout="diff --git a/f b/f\n")
    )
    assert _has_uncommitted_working_tree_changes(Path(".")) is True

    process_fake.answer(lambda call: True, ProcessAnswer(returncode=0, stdout=""))
    assert _has_uncommitted_working_tree_changes(Path(".")) is False


def test_resolve_main_branch_fallback_base(process_fake: ProcessFake) -> None:
    """Verify base resolution on main using git tags and parent commits."""
    from devops_cli.ai.review.runner import _resolve_main_branch_fallback_base

    # Tag exists with non-empty diff
    process_fake.answer(lambda call: True, ProcessAnswer(returncode=0, stdout="diff content\n"))
    with patch("devops_cli.git.operations.get_latest_git_tag", return_value="v0.2.18"):
        assert _resolve_main_branch_fallback_base(Path("."), "main") == "v0.2.18"

    # Tag exists but diff is empty -> fallback to parent commit main~1
    process_fake.answer(
        lambda call: any("main~1" in arg for arg in call.argv),
        ProcessAnswer(returncode=0, stdout="commit-hash\n"),
    )
    process_fake.answer(
        lambda call: "diff" in call.argv,
        ProcessAnswer(returncode=0, stdout=""),
    )

    with patch("devops_cli.git.operations.get_latest_git_tag", return_value="v0.2.18"):
        assert _resolve_main_branch_fallback_base(Path("."), "main") == "main~1"


def test_resolve_branch_targets() -> None:
    """Verify resolution of branch target and effective base across branch permutations."""
    from devops_cli.ai.review.runner import _resolve_branch_targets

    # 1. On a topic branch, passing 'main' (which equals base 'main') -> diff current branch against main
    with (
        patch(
            "devops_cli.ai.review.runner._get_current_git_branch", return_value="feat/20-example"
        ),
        patch("devops_cli.ai.review.runner._detect_base_branch", return_value="main"),
    ):
        branch, base, is_wt = _resolve_branch_targets(Path("."), "main", "main")
        assert branch == "feat/20-example"
        assert base == "main"
        assert is_wt is False

    # 2. On main branch with uncommitted changes -> diff main against HEAD
    with (
        patch("devops_cli.ai.review.runner._get_current_git_branch", return_value="main"),
        patch("devops_cli.ai.review.runner._detect_base_branch", return_value="main"),
        patch(
            "devops_cli.ai.review.runner._has_uncommitted_working_tree_changes", return_value=True
        ),
    ):
        branch, base, is_wt = _resolve_branch_targets(Path("."), None, "main")
        assert branch == "main"
        assert base == "HEAD"
        assert is_wt is True

    # 3. On main branch with clean tree -> diff main against fallback base
    with (
        patch("devops_cli.ai.review.runner._get_current_git_branch", return_value="main"),
        patch("devops_cli.ai.review.runner._detect_base_branch", return_value="main"),
        patch(
            "devops_cli.ai.review.runner._has_uncommitted_working_tree_changes", return_value=False
        ),
        patch(
            "devops_cli.ai.review.runner._resolve_main_branch_fallback_base", return_value="v0.2.18"
        ),
    ):
        branch, base, is_wt = _resolve_branch_targets(Path("."), "main", "main")
        assert branch == "main"
        assert base == "v0.2.18"
        assert is_wt is False

    # 4. Standard feature branch -> normal diff
    with (
        patch("devops_cli.ai.review.runner._get_current_git_branch", return_value="feat/test"),
        patch("devops_cli.ai.review.runner._detect_base_branch", return_value="main"),
    ):
        branch, base, is_wt = _resolve_branch_targets(Path("."), "feat/test", "main")
        assert branch == "feat/test"
        assert base == "main"
        assert is_wt is False


def test_prepare_branch_content_on_main_and_base_switching(
    process_fake: ProcessFake,
) -> None:
    """Verify _prepare_branch_content properly prepares pages on main and base-passed branches."""
    from devops_cli.ai.review.runner import _prepare_branch_content

    process_fake.answer(
        "git diff",
        ProcessAnswer(
            returncode=0,
            stdout="diff --git a/app.py b/app.py\n+print('hello')\n",
        ),
    )

    # Calling with 'main' from feat/19-example
    with (
        patch(
            "devops_cli.ai.review.runner._get_current_git_branch", return_value="feat/19-example"
        ),
        patch("devops_cli.ai.review.runner._detect_base_branch", return_value="main"),
        patch("devops_cli.git.operations.resolve_merge_base", return_value="base-sha"),
        patch("devops_cli.git.operations.list_changed_files", return_value=[]),
    ):
        pages, title, target, _ = _prepare_branch_content(
            "main", "main", REPO_ROOT, working_directory=REPO_ROOT
        )
        assert (len(pages) >= 1, "feat/19-example" in title, "main" in title, target) == (
            True,
            True,
            True,
            "feat/19-example",
        )

    # Calling on main with uncommitted changes
    with (
        patch("devops_cli.ai.review.runner._get_current_git_branch", return_value="main"),
        patch("devops_cli.ai.review.runner._detect_base_branch", return_value="main"),
        patch(
            "devops_cli.ai.review.runner._has_uncommitted_working_tree_changes", return_value=True
        ),
        patch("devops_cli.git.operations.list_changed_files", return_value=[]),
    ):
        pages, title, target, _ = _prepare_branch_content(
            None, "main", REPO_ROOT, working_directory=REPO_ROOT
        )
        assert (len(pages) >= 1, "main" in title, "HEAD" in title, target) == (
            True,
            True,
            True,
            "main",
        )
