"""Regression tests for review worktree isolation, change set scoping, and coverage (#1047)."""

from __future__ import annotations

import hashlib
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from devops_cli.ai.analyze.cache import FileAnalysisMeta
from devops_cli.ai.review.chunker import _extract_header_filenames
from devops_cli.ai.review.path_classes import (
    classify_path,
    is_fixture_path,
    load_path_classes,
)
from devops_cli.ai.review.pipeline import (
    ReviewPipelineOrchestrator,
    _compute_coverage_matrix,
    _try_reuse_cached_analysis_meta,
)
from devops_cli.ai.review.profile import ReviewProfiler
from devops_cli.git.operations import (
    git_show_toplevel,
    list_changed_files,
)
from devops_cli.git.worktree import (
    review_worktrees_context,
)


def _init_git_repo(repo_dir: Path) -> None:
    """Initialize a git repo with configured user."""
    subprocess.run(["git", "init", "-b", "main", str(repo_dir)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo_dir), "config", "user.name", "Test Runner"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo_dir), "config", "user.email", "runner@example.com"],
        check=True,
        capture_output=True,
    )


def test_branch_review_worktree_isolation_regression(tmp_path: Path) -> None:
    """In tmp_path repo with base and branch commit changing app.py and uncommitted extra().

    Branch review metadata for app.py has commit content_hash and no extra in key_symbols.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)

    app_py = repo / "app.py"
    app_py.write_text("def main():\n    pass\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "app.py"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "initial"], check=True, capture_output=True
    )

    subprocess.run(
        ["git", "-C", str(repo), "checkout", "-b", "feature"], check=True, capture_output=True
    )
    commit_code = "def compute():\n    return 42\n"
    app_py.write_text(commit_code, encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-am", "feature commit"],
        check=True,
        capture_output=True,
    )
    expected_hash = hashlib.sha256(commit_code.encode("utf-8")).hexdigest()

    # Working tree uncommitted edit: adds extra()
    uncommitted_code = "def compute():\n    return 42\n\ndef extra():\n    return 'uncommitted'\n"
    app_py.write_text(uncommitted_code, encoding="utf-8")

    session_id = "test-iso-regression"
    with review_worktrees_context(
        repo,
        commit_rev="feature",
        base_rev="main",
        session_id=session_id,
    ) as rw:
        assert (
            rw.commit_worktree is not None,
            rw.commit_worktree.is_relative_to(tmp_path),
        ) == (True, True)
        orchestrator = ReviewPipelineOrchestrator(
            session_id=session_id,
            target_dir=rw.commit_worktree,
        )
        metas = orchestrator.run_pre_analysis_refresh(
            target_dir=rw.commit_worktree,
            target_type="branch",
            target_ref="feature",
        )

        app_meta = metas.get("app.py")
        assert app_meta is not None
        has_extra = "extra" in app_meta.key_symbols
        has_compute = "compute" in app_meta.key_symbols
        assert (app_meta.content_hash, has_extra, has_compute) == (
            expected_hash,
            False,
            True,
        )


def test_pre_analysis_cache_reuse_bypassing_mtime(tmp_path: Path) -> None:
    """Pre-analysis of worktree reuses checkout's cached metadata when content hash matches."""
    sample_file = tmp_path / "module.py"
    code = "def add(a, b):\n    return a + b\n"
    sample_file.write_text(code, encoding="utf-8")
    content_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()

    cached = FileAnalysisMeta(
        path="module.py",
        content_hash=content_hash,
        size_bytes=len(code.encode("utf-8")),
        key_symbols=["add"],
        pseudocode=["return sum"],
        last_analyzed="2026-01-01T00:00:00+00:00",
    )

    newer_mtime = datetime(2026, 10, 7, 0, 0, 0, tzinfo=UTC)
    reused = _try_reuse_cached_analysis_meta(cached, sample_file, newer_mtime, bypass_mtime=True)
    assert reused is not None
    assert (reused.content_hash, reused.key_symbols) == (content_hash, ["add"])


def test_deleted_files_and_renames_diff_parsing(tmp_path: Path) -> None:
    """Git diff change set parsing marks deleted files and keeps old path on renames."""
    repo = tmp_path / "repo_diff"
    repo.mkdir()
    _init_git_repo(repo)

    del_file = repo / "to_delete.py"
    del_file.write_text("print('delete me')\n", encoding="utf-8")
    ren_file = repo / "old_name.py"
    ren_file.write_text("print('rename me')\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "init files"], check=True, capture_output=True
    )

    subprocess.run(
        ["git", "-C", str(repo), "checkout", "-b", "diff_branch"], check=True, capture_output=True
    )
    subprocess.run(["git", "-C", str(repo), "rm", "to_delete.py"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "mv", "old_name.py", "new_name.py"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "delete and rename"],
        check=True,
        capture_output=True,
    )

    changes = list_changed_files(repo, "main", "diff_branch")
    by_path = {c.path: c for c in changes}

    assert "to_delete.py" in by_path
    assert "new_name.py" in by_path

    del_change = by_path["to_delete.py"]
    ren_change = by_path["new_name.py"]

    assert (del_change.change_type, ren_change.change_type, ren_change.old_path) == (
        "deleted",
        "renamed",
        "old_name.py",
    )


def test_chunker_rename_extracts_target_path() -> None:
    """Header extraction from rename diff tracks the target path at head."""
    page = (
        "diff --git a/old_dir/foo.py b/new_dir/foo.py\n"
        "similarity index 100%\n"
        "rename from old_dir/foo.py\n"
        "rename to new_dir/foo.py\n"
    )
    extracted = _extract_header_filenames(page)
    assert extracted == ["new_dir/foo.py"]


def test_path_classes_loading_and_fixture_skipping(tmp_path: Path) -> None:
    """Path classes loaded from configuration; fixtures and golden sets go to secret scanner only."""
    config_dir = tmp_path / ".devops"
    config_dir.mkdir()
    config_file = config_dir / "review.toml"
    config_file.write_text(
        '[paths]\nsrc = ["src/**"]\ntest = ["tests/**"]\nfixture = ["tests/fixtures/**", "tests/golden/**"]\n',
        encoding="utf-8",
    )

    classes = load_path_classes(repo_root=tmp_path)
    assert ("src/**" in classes["src"], "tests/golden/**" in classes["fixture"]) == (True, True)

    assert classify_path(Path("src/app.py"), classes) == "src"
    assert classify_path(Path("tests/fixtures/sample.json"), classes) == "fixture"
    assert classify_path(Path("tests/golden/data.txt"), classes) == "fixture"
    assert is_fixture_path(Path("tests/fixtures/sample.json"), classes) is True
    assert is_fixture_path(Path("src/app.py"), classes) is False


def test_coverage_matrix_and_markdown_section(tmp_path: Path) -> None:
    """Coverage matrix records tool file statuses and formats ## Coverage in review.md."""
    tools = ["Bandit", "Gitleaks", "Semgrep"]
    files = ["src/app.py", "tests/fixtures/creds.env"]
    path_classes = {
        "src": ["src/**"],
        "fixture": ["tests/fixtures/**"],
    }

    tool_states = {
        "Bandit": "ran",
        "Gitleaks": "ran",
        "Semgrep": "timed out after 120 s",
    }

    def resolve_fn(f: str) -> Path:
        return tmp_path / f

    matrix = _compute_coverage_matrix(tools, files, resolve_fn, tool_states, path_classes)

    bandit_cov = (matrix["Bandit"]["src/app.py"], matrix["Bandit"]["tests/fixtures/creds.env"])
    gitleaks_cov = (
        matrix["Gitleaks"]["src/app.py"],
        matrix["Gitleaks"]["tests/fixtures/creds.env"],
    )
    semgrep_cov = matrix["Semgrep"]["src/app.py"]

    assert (bandit_cov, gitleaks_cov, semgrep_cov) == (
        ("scanned", "skipped(fixture)"),
        ("scanned", "scanned"),
        ("timed out after 120 s"),
    )

    orchestrator = ReviewPipelineOrchestrator(session_id="test-cov", target_dir=tmp_path)
    orchestrator.coverage = matrix
    section = "\n".join(orchestrator._build_coverage_section())
    assert "## Coverage" in section
    assert "| Tool | File | Status |" in section
    assert "| Bandit | `src/app.py` | scanned |" in section
    assert "| Bandit | `tests/fixtures/creds.env` | skipped(fixture) |" in section
    assert "| Gitleaks | `tests/fixtures/creds.env` | scanned |" in section


def test_review_profile_coverage_and_partial_context() -> None:
    """ReviewProfiler builds profile with coverage matrix and partial_context."""
    profiler = ReviewProfiler()
    test_cov = {"Gitleaks": {"app.py": "scanned"}}
    profiler.set_coverage(test_cov)
    profiler.set_partial_context(True)

    profile = profiler.build(session_id="test-p", target="target-p", files=1)
    assert (profile.coverage, profile.partial_context) == (test_cov, True)


def test_git_show_toplevel_resolution(tmp_path: Path) -> None:
    """git_show_toplevel resolves repository root from single-file or nested directory."""
    repo = tmp_path / "repo_root_test"
    repo.mkdir()
    _init_git_repo(repo)

    sub = repo / "sub" / "dir"
    sub.mkdir(parents=True)
    file_path = sub / "test.py"
    file_path.write_text("x = 1\n", encoding="utf-8")

    resolved_from_sub = git_show_toplevel(sub)
    resolved_from_file = git_show_toplevel(file_path)

    expected = repo.resolve()
    assert (resolved_from_sub, resolved_from_file) == (expected, expected)


def test_run_pr_review_workflow_partial_context(tmp_path: Path) -> None:
    """When fetch_pr_head returns None, review runs against head_dir with partial_context=True."""
    from unittest.mock import MagicMock, patch

    from devops_cli.commands.review import _run_pr_review_workflow

    pull = MagicMock()
    pull.base.sha = "base-sha"
    head_dir = tmp_path / "head_dir"
    head_dir.mkdir()

    with (
        patch("devops_cli.git.worktree.fetch_pr_head", return_value=None),
        patch("devops_cli.commands.review._execute_review_workflow", return_value=[]) as mock_exec,
    ):
        result = _run_pr_review_workflow(
            pages=["page1"],
            title="PR #42: Test",
            agents_md="agents",
            pull=pull,
            number=42,
            head_dir=head_dir,
            base_revision=None,
            all_personas=False,
            persona=None,
            summary=False,
            clients=MagicMock(),
            stage_flags=MagicMock(),
            concurrency=None,
            parallel=True,
            full=False,
            session_id="test-pr-session",
        )

        assert result == []
        mock_exec.assert_called_once()
        _, kwargs = mock_exec.call_args
        assert (kwargs["partial_context"], kwargs["target_dir"]) == (True, head_dir)


def test_run_pr_review_workflow_with_worktree(tmp_path: Path) -> None:
    """When fetch_pr_head succeeds, review runs against detached worktree with partial_context=False."""
    from unittest.mock import MagicMock, patch

    from devops_cli.commands.review import _run_pr_review_workflow
    from devops_cli.git.worktree import ReviewWorktrees

    pull = MagicMock()
    pull.base.sha = "base-sha"
    head_dir = tmp_path / "head_dir"
    head_dir.mkdir()
    wt_dir = tmp_path / "commit_wt"
    wt_dir.mkdir()

    mock_rw = ReviewWorktrees(commit_worktree=wt_dir, base_worktree=None, partial_context=False)

    with (
        patch("devops_cli.git.worktree.fetch_pr_head", return_value="commit-sha-42"),
        patch("devops_cli.git.worktree.review_worktrees_context") as mock_ctx,
        patch("devops_cli.commands.review._execute_review_workflow", return_value=[]) as mock_exec,
    ):
        mock_ctx.return_value.__enter__.return_value = mock_rw
        result = _run_pr_review_workflow(
            pages=["page1"],
            title="PR #42: Test",
            agents_md="agents",
            pull=pull,
            number=42,
            head_dir=head_dir,
            base_revision=None,
            all_personas=False,
            persona=None,
            summary=False,
            clients=MagicMock(),
            stage_flags=MagicMock(),
            concurrency=None,
            parallel=True,
            full=False,
            session_id="test-pr-session",
        )

        assert result == []
        mock_exec.assert_called_once()
        _, kwargs = mock_exec.call_args
        assert (kwargs["partial_context"], kwargs["target_dir"]) == (False, wt_dir)
