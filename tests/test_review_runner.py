"""Unit tests for AI review runner, prompt construction, and session persistence."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from devops_cli.ai.personas import PERSONAS, Persona
from devops_cli.ai.review.runner import (
    ReviewClients,
    _build_path_prompt,
    _build_recompose_prompt,
    _build_segment_review_prompt,
    _calculate_parallel_review_workers,
    _collect_file_blocks,
    _collect_files,
    _execute_findings_validation,
    _execute_review_segments,
    _get_reviews_base_dir,
    _git_repo_root,
    _is_allowed_review_boundary,
    _load_agents_md,
    _make_review_clients,
    _personas_to_run,
    _prepare_branch_content,
    _prepare_path_content,
    _prepare_pr_content,
    _resolve_review_clients,
    _review_session_dir,
    _run_persona_loop,
    _run_review,
    _save_findings_json,
    _save_persona_review,
    _save_segments,
    _write_summary,
)
from devops_cli.ai.review_schema import (
    Finding,
    ReviewResult,
    ReviewSessionPayload,
    SavedFinding,
)
from devops_cli.commands.review import app as review_app
from devops_cli.config.settings import Settings
from devops_cli.core.repo import is_ignored_by_git
from devops_cli.models.vulnerability import DependencySpec, NetworkReference
from devops_cli.output import (
    render_review_raw,
    render_review_result,
)


def test_rendering_helpers() -> None:
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
        positive_observations=["Clean code style"],
        summary="Summary of issues",
        raw_markdown="# Security Review",
    )
    render_review_result(persona_def, res)
    render_review_raw(persona_def, "## Raw review text")


def test_runner_file_and_repo_helpers(tmp_path: Path) -> None:
    """Verify runner repository traversal, git boundary, and agents.md loading."""
    st = Settings()
    st.repos.base_dir = tmp_path
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init", str(repo_dir)], check=True, capture_output=True)
    (repo_dir / "src").mkdir()
    sample_file = repo_dir / "src" / "app.py"
    sample_file.write_text("print('hello')\n")
    (repo_dir / "AGENTS.md").write_text("# Agents Guidelines\n")

    assert _git_repo_root(sample_file) == repo_dir
    assert _is_allowed_review_boundary(sample_file, st) is True

    agents_content = _load_agents_md(repo_dir)
    assert "Agents Guidelines" in agents_content

    assert is_ignored_by_git(repo_dir, sample_file) is False

    files = _collect_files(repo_dir / "src", "*.py")
    assert "print('hello')" in files

    (repo_dir / ".gitignore").write_text("*.py\n")
    assert is_ignored_by_git(repo_dir, sample_file) is True
    (repo_dir / ".gitignore").unlink()

    blocks = _collect_file_blocks(repo_dir / "src", "*.py")
    assert len(blocks) >= 1


def test_runner_persona_and_prompts() -> None:
    """Verify persona filtering and prompt generation logic."""
    personas = _personas_to_run(all_personas=True, persona=None)
    assert len(personas) >= 5

    p_devsecops = _personas_to_run(all_personas=False, persona=Persona.DEVSECOPS)
    assert p_devsecops == [PERSONAS[Persona.DEVSECOPS]]

    prompt = _build_path_prompt("print('hello')", "Agents context")
    assert "print('hello')" in prompt
    assert "Agents context" in prompt

    pd = PERSONAS[Persona.DEVSECOPS]
    with patch("devops_cli.ai.rag.investigator.investigate_rag_context", return_value=None):
        seg_prompt = _build_segment_review_prompt(
            "diff block", "Title", 1, 2, {}, _build_path_prompt, pd
        )
    assert '"total_files": 2' in seg_prompt
    assert '"current_file_index": 1' in seg_prompt

    recompose_prompt = _build_recompose_prompt("Test Title", {}, ["response 1"], pd, [])
    prompt_lower = recompose_prompt.lower()
    assert "recompose" in prompt_lower or "consolidate" in prompt_lower or "review" in prompt_lower


def test_runner_session_persistence(tmp_path: Path) -> None:
    """Verify saving of persona reviews, findings, segments, and summaries."""
    base_dir = _get_reviews_base_dir()
    assert base_dir.exists()

    session_dir = _review_session_dir(str(tmp_path))
    assert session_dir.exists()

    finding = Finding(
        severity="MEDIUM",
        title="Arch issue",
        description="Desc",
        location="src/main.py:20",
        fix="Refactor",
    )
    res = ReviewResult(
        persona=Persona.ARCHITECT,
        findings=[finding],
        raw_markdown="# Review",
    )

    pd = PERSONAS[Persona.ARCHITECT]
    _save_persona_review(pd, res, session_dir)
    assert (session_dir / "architect-review.md").exists()

    _save_findings_json([(pd, res)], session_dir, show_status=True)
    assert (session_dir / "findings.json").exists()

    _save_segments(["page 1", "page 2"], session_dir)
    assert (session_dir / "segment-1.md").exists()

    _write_summary("Test Title", session_dir, ["page 1"], [(pd, res)])
    assert (session_dir / "summary.md").exists()


def test_make_and_resolve_review_clients() -> None:
    """Verify review client factory functions."""
    st = Settings()
    clients = _make_review_clients(st)
    assert isinstance(clients, ReviewClients)

    res_clients = _resolve_review_clients(st)
    assert res_clients is not None


def test_prepare_content_helpers(tmp_path: Path) -> None:
    """Verify content preparation for paths, branches, and PRs."""
    test_file = Path("src/devops_cli/main.py")

    pages, title, agents_md = _prepare_path_content(test_file, "*")
    assert len(pages) >= 1
    assert "main.py" in title

    import subprocess

    mock_cp = subprocess.CompletedProcess(
        args=["git"],
        returncode=0,
        stdout="diff --git a/test.py b/test.py\n+def foo(): return 42\n",
        stderr="",
    )

    with patch("devops_cli.ai.review.runner._run_subprocess", return_value=mock_cp):
        b_pages, b_title, b_agents, b_target = _prepare_branch_content(
            "feat/test", "main", Path(".")
        )
        assert len(b_pages) >= 1
        assert "feat/test" in b_title
        assert b_target == "feat/test"

    with patch("devops_cli.github.client.GitHubClient") as mock_gh_cls:
        mock_gh = mock_gh_cls.return_value
        mock_gh.get_pull.return_value = MagicMock(title="Mock PR Title")
        mock_gh.get_pr_diff.return_value = "diff --git a/test.py b/test.py\n+content\n"
        pr_pages, pr_title, pr_agents, pull, repo = _prepare_pr_content(
            123, repo_arg="owner/repo", token="ghp_test"
        )
        assert len(pr_pages) >= 1
        assert "PR #123" in pr_title


def test_run_review_and_persona_loop(tmp_path: Path) -> None:
    """Verify review execution and persona multi-step loop."""
    valid_json_response = json.dumps(
        {
            "findings": [
                {
                    "severity": "HIGH",
                    "location": "src/db.py:12",
                    "title": "SQL Injection",
                    "description": "Desc",
                    "fix": "Use params",
                }
            ],
            "recommendation": "REQUEST CHANGES",
            "summary": "Found SQL Injection",
        }
    )
    mock_client = MagicMock()
    mock_client.chat.return_value = valid_json_response
    mock_client.complete.return_value = valid_json_response
    mock_client.backend_info = "mock-backend"

    clients = ReviewClients(analysis=mock_client, compose=mock_client)
    pd = PERSONAS[Persona.DEVSECOPS]

    with patch("devops_cli.ai.rag.investigator.investigate_rag_context", return_value=None):
        result = _run_review(
            pages=["file content page"],
            title="Test Review",
            persona=pd,
            clients=clients,
            agents_md="",
            build_prompt=_build_path_prompt,
            session_dir=tmp_path,
        )
        assert result is not None
        assert isinstance(result, ReviewResult)
        assert len(result.findings) == 1

        completed_list = _run_persona_loop(
            pages=["file content page"],
            title="Test Review",
            build_prompt=_build_path_prompt,
            clients=clients,
            agents_md="",
            all_personas=False,
            persona=Persona.DEVSECOPS,
        )
        assert len(completed_list) == 1


def test_review_runner_extended_branches(tmp_path: Path) -> None:
    """Verify session lookup, markdown formatting, fallback join, and multi-segment review."""
    from devops_cli.ai.review.runner import (
        _fallback_join,
        _find_session_dir,
        _log_segment_empty,
        _log_segment_error,
        _print_review,
        _review_to_markdown,
    )

    # 1. Fallback join deduplication
    assert _fallback_join(["line 1\nline 2", "line 2\nline 3"]) == "line 1\nline 2\n\nline 3"

    # 2. Review to markdown with unverified and mitigated findings
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
        positive_observations=["Good architecture"],
        summary="Review complete",
    )
    md = _review_to_markdown(res_mit)
    assert "*(mitigated)*" in md
    assert "*(unverified)*" in md
    assert "Good architecture" in md

    # 3. Print review helpers
    pd = PERSONAS[Persona.DEVSECOPS]
    _print_review(pd, "")
    _print_review(pd, "## Plain markdown review")

    # 4. Log helpers
    _log_segment_error("file.py", 1.0, " [ollama]", 1)
    _log_segment_error("file.py", 1.0, " [ollama]", 3)
    _log_segment_empty("file.py", 1.0, " [ollama]", 1)
    _log_segment_empty("file.py", 1.0, " [ollama]", 3)

    # 5. Session directory lookup
    with patch("devops_cli.ai.review.runner._get_reviews_base_dir", return_value=tmp_path):
        s1 = tmp_path / "20260826-120000-session1"
        s1.mkdir()
        (s1 / "findings.json").write_text("{}", encoding="utf-8")
        found = _find_session_dir("session1")
        assert found == s1


def test_review_runner_dry_run_and_summary_metas(tmp_path: Path) -> None:
    """Verify dry-run mock constructors, summary generation with file metadata, and error branches."""
    from devops_cli.ai.review.runner import (
        _build_dry_run_persona_result,
        _build_dry_run_segment_result,
        _write_summary,
    )
    from devops_cli.models.ai import FileAnalysisMeta

    # 1. Dry run constructors
    seg_res = _build_dry_run_segment_result("app.py", "app.py analysis")
    assert seg_res.recommendation == "APPROVE"
    assert len(seg_res.findings) == 1
    assert "[dry-run]" in seg_res.findings[0].title

    persona_res = _build_dry_run_persona_result("Review Title", "devsecops", 3)
    assert persona_res.recommendation == "APPROVE"
    assert len(persona_res.findings) == 1

    # 2. Write summary with analysis metadata
    meta = FileAnalysisMeta(
        path="src/app.py",
        language="python",
        primary_purpose="Main web entry point",
        complexity_score="medium",
        key_symbols=["App", "main", "run_server"],
    )
    analysis_metas = {"src/app.py": meta}
    pd = PERSONAS[Persona.DEVSECOPS]

    session_dir = tmp_path / "session_with_metas"
    session_dir.mkdir()

    _write_summary(
        title="Meta Review",
        session_dir=session_dir,
        pages=["segment 1 content", "segment 2 content"],
        completed=[(pd, persona_res)],
        analysis_metas=analysis_metas,
    )

    summary_text = (session_dir / "summary.md").read_text(encoding="utf-8")
    assert "Analysis Metadata" in summary_text
    assert "Main web entry point" in summary_text
    assert "src/app.py" in summary_text
    assert "Symbols: App, main, run_server" in summary_text


def test_review_cli_commands(tmp_path: Path) -> None:
    """Verify review findings, verify, stats, and export-feedback commands."""
    runner = CliRunner()
    session_dir = tmp_path / "20260826-000000-sample-session"
    session_dir.mkdir(parents=True)

    findings = [
        SavedFinding(
            id=1,
            title="Insecure Port Binding",
            severity="HIGH",
            location="src/app.py:10",
            status="UNVERIFIED",
            persona="devsecops",
            persona_title="Principal DevSecOps Engineer",
            recommendation="REQUEST CHANGES",
            confidence_score=0.90,
        ),
        SavedFinding(
            id=2,
            title="Missing Docstring",
            severity="LOW",
            location="src/app.py:20",
            status="VERIFIED",
            persona="qa",
            persona_title="Senior QA Engineer",
            recommendation="COMMENT",
            confidence_score=0.80,
        ),
    ]
    payload = ReviewSessionPayload(
        session_id="sample-session",
        created_at="2026-08-26T00:00:00",
        target_type="path",
        target="src/",
        findings=findings,
    )
    (session_dir / "findings.json").write_text(payload.model_dump_json(indent=2), encoding="utf-8")

    with patch("devops_cli.ai.review.runner._get_reviews_base_dir", return_value=tmp_path):
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


def test_detect_base_branch(tmp_path: Path) -> None:
    """Verify base branch detection and fallback handling."""
    from devops_cli.ai.review.runner import _detect_base_branch

    with patch("devops_cli.ai.review.runner._run_subprocess") as mock_sub:
        mock_sub.return_value = MagicMock(returncode=0, stdout="origin/release/v0.2.0\n")
        b = _detect_base_branch(tmp_path, preferred_base="release/v0.2.0")
        assert "release/v0.2.0" in b

        mock_sub.return_value = MagicMock(returncode=1, stdout="", stderr="err")
        b_fallback = _detect_base_branch(tmp_path)
        assert b_fallback in ("main", "master")


def test_fallback_join() -> None:
    """Verify fallback list joining helper."""
    from devops_cli.ai.review.runner import _fallback_join

    joined = _fallback_join(["item 1", "item 2", "item 3"])
    assert "item 1" in joined and "item 2" in joined


def test_is_allowed_review_boundary() -> None:
    """Verify review path boundary isolation and forbidden system path rejections."""
    from devops_cli.ai.review.runner import _is_allowed_review_boundary
    from devops_cli.config.settings import Settings

    st = Settings()
    assert _is_allowed_review_boundary(Path("src/app.py"), st) is True
    assert _is_allowed_review_boundary(Path("/etc/shadow"), st) is False
    assert _is_allowed_review_boundary(Path("/etc/passwd"), st) is False


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
        positive_observations=["Clean typing"],
        summary="Architecture is mostly sound.",
    )
    md = _review_to_markdown(res)
    assert "Tight Coupling" in md
    assert "Clean typing" in md
    assert "Architecture is mostly sound" in md


def test_make_review_clients() -> None:
    """Verify creation of analysis and compose review clients."""
    from devops_cli.ai.review.runner import _make_review_clients
    from devops_cli.config.settings import Settings

    st = Settings()
    clients = _make_review_clients(st)
    assert clients.analysis is not None
    assert clients.compose is not None


def test_get_current_git_branch() -> None:
    """Verify active branch name detection and detached HEAD handling."""
    from devops_cli.ai.review.runner import _get_current_git_branch

    # Attached branch
    cp_branch = subprocess.CompletedProcess(
        args=["git"], returncode=0, stdout="release/v0.2.20\n", stderr=""
    )
    with patch("devops_cli.ai.review.runner._run_subprocess", return_value=cp_branch):
        assert _get_current_git_branch(Path(".")) == "release/v0.2.20"

    # Detached HEAD
    cp_head = subprocess.CompletedProcess(args=["git"], returncode=0, stdout="HEAD\n", stderr="")
    with patch("devops_cli.ai.review.runner._run_subprocess", return_value=cp_head):
        assert _get_current_git_branch(Path(".")) == ""

    # Failure
    cp_fail = subprocess.CompletedProcess(args=["git"], returncode=1, stdout="", stderr="fatal")
    with patch("devops_cli.ai.review.runner._run_subprocess", return_value=cp_fail):
        assert _get_current_git_branch(Path(".")) == ""


def test_has_uncommitted_working_tree_changes() -> None:
    """Verify detection of staged and unstaged working tree changes."""
    from devops_cli.ai.review.runner import _has_uncommitted_working_tree_changes

    cp_dirty = subprocess.CompletedProcess(
        args=["git"], returncode=0, stdout="diff --git a/f b/f\n", stderr=""
    )
    with patch("devops_cli.ai.review.runner._run_subprocess", return_value=cp_dirty):
        assert _has_uncommitted_working_tree_changes(Path(".")) is True

    cp_clean = subprocess.CompletedProcess(args=["git"], returncode=0, stdout="", stderr="")
    with patch("devops_cli.ai.review.runner._run_subprocess", return_value=cp_clean):
        assert _has_uncommitted_working_tree_changes(Path(".")) is False


def test_resolve_main_branch_fallback_base() -> None:
    """Verify base resolution on main using git tags and parent commits."""
    from devops_cli.ai.review.runner import _resolve_main_branch_fallback_base

    # Tag exists with non-empty diff
    cp_diff = subprocess.CompletedProcess(
        args=["git"], returncode=0, stdout="diff content\n", stderr=""
    )
    with (
        patch("devops_cli.git.operations.get_latest_git_tag", return_value="v0.2.18"),
        patch("devops_cli.ai.review.runner._run_subprocess", return_value=cp_diff),
    ):
        assert _resolve_main_branch_fallback_base(Path("."), "main") == "v0.2.18"

    # Tag exists but diff is empty -> fallback to parent commit main~1
    cp_empty = subprocess.CompletedProcess(args=["git"], returncode=0, stdout="", stderr="")
    cp_parent_ok = subprocess.CompletedProcess(
        args=["git"], returncode=0, stdout="commit-hash\n", stderr=""
    )

    def _mock_subp(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if "diff" in cmd:
            return cp_empty
        if len(cmd) > 4 and "main~1" in cmd[4]:
            return cp_parent_ok
        return cp_empty

    with (
        patch("devops_cli.git.operations.get_latest_git_tag", return_value="v0.2.18"),
        patch("devops_cli.ai.review.runner._run_subprocess", side_effect=_mock_subp),
    ):
        assert _resolve_main_branch_fallback_base(Path("."), "main") == "main~1"


def test_resolve_branch_targets() -> None:
    """Verify resolution of branch target and effective base across branch permutations."""
    from devops_cli.ai.review.runner import _resolve_branch_targets

    # 1. On release branch, passing 'main' (which equals base 'main') -> diff current branch against main
    with (
        patch(
            "devops_cli.ai.review.runner._get_current_git_branch", return_value="release/v0.2.20"
        ),
        patch("devops_cli.ai.review.runner._detect_base_branch", return_value="main"),
    ):
        branch, base, is_wt = _resolve_branch_targets(Path("."), "main", "main")
        assert branch == "release/v0.2.20"
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


def test_prepare_branch_content_on_main_and_base_switching() -> None:
    """Verify _prepare_branch_content properly prepares pages on main and base-passed branches."""
    from devops_cli.ai.review.runner import _prepare_branch_content

    mock_diff = subprocess.CompletedProcess(
        args=["git"],
        returncode=0,
        stdout="diff --git a/app.py b/app.py\n+print('hello')\n",
        stderr="",
    )

    # Calling with 'main' from release/v0.2.19
    with (
        patch(
            "devops_cli.ai.review.runner._get_current_git_branch", return_value="release/v0.2.19"
        ),
        patch("devops_cli.ai.review.runner._detect_base_branch", return_value="main"),
        patch("devops_cli.ai.review.runner._run_subprocess", return_value=mock_diff),
    ):
        pages, title, agents, target = _prepare_branch_content("main", "main", Path("."))
        assert len(pages) >= 1
        assert "release/v0.2.19" in title
        assert "main" in title
        assert target == "release/v0.2.19"

    # Calling on main with uncommitted changes
    with (
        patch("devops_cli.ai.review.runner._get_current_git_branch", return_value="main"),
        patch("devops_cli.ai.review.runner._detect_base_branch", return_value="main"),
        patch(
            "devops_cli.ai.review.runner._has_uncommitted_working_tree_changes", return_value=True
        ),
        patch("devops_cli.ai.review.runner._run_subprocess", return_value=mock_diff),
    ):
        pages, title, agents, target = _prepare_branch_content(None, "main", Path("."))
        assert len(pages) >= 1
        assert "main" in title
        assert "HEAD" in title
        assert target == "main"


def test_calculate_parallel_review_workers() -> None:
    """Verify worker capacity calculation honoring concurrency, configs, and upper bounds."""
    from devops_cli.config.defaults import (
        DEFAULT_REVIEW_CONCURRENCY,
        DEFAULT_REVIEW_MAX_CONCURRENCY,
    )

    clients = MagicMock()
    clients.analysis._config.ollama_max_parallel = 2
    clients.analysis._config.ollama_urls = ["http://example.com:11434"]

    # 1. Explicit concurrency override
    workers_explicit = _calculate_parallel_review_workers(clients, num_tasks=10, concurrency=6)
    workers_clamped = _calculate_parallel_review_workers(clients, num_tasks=2, concurrency=6)
    workers_min = _calculate_parallel_review_workers(clients, num_tasks=5, concurrency=-1)
    assert (workers_explicit, workers_clamped, workers_min) == (6, 2, 1)

    # 2. Default calculation based on ollama_urls
    workers_default = _calculate_parallel_review_workers(clients, num_tasks=10)
    assert workers_default == DEFAULT_REVIEW_CONCURRENCY

    # 3. High capacity capped by DEFAULT_REVIEW_MAX_CONCURRENCY
    clients.analysis._config.ollama_urls = [f"http://example.com:{11434 + i}" for i in range(10)]
    workers_max = _calculate_parallel_review_workers(clients, num_tasks=20)
    assert workers_max == DEFAULT_REVIEW_MAX_CONCURRENCY


def test_execute_review_segments_parallel_and_error_handling() -> None:
    """Verify _execute_review_segments runs in parallel and isolates segment failures."""
    import threading
    import time

    clients = MagicMock()
    clients.analysis._config.ollama_max_parallel = 2
    clients.analysis._config.ollama_urls = ["http://example.com:11434"]
    persona = PERSONAS[Persona.DEVSECOPS]

    pages = ["diff 1", "diff 2", "diff 3"]
    active_workers = 0
    max_active = 0
    lock = threading.Lock()

    def _mock_attempt(clients, sys_prompt, user_prompt, label, suffix):
        nonlocal active_workers, max_active
        with lock:
            active_workers += 1
            max_active = max(max_active, active_workers)
        time.sleep(0.04)
        try:
            if "segment 2/3" in label:
                raise RuntimeError("LLM failure on segment 2")
            return f"Review for {label}"
        finally:
            with lock:
                active_workers -= 1

    with (
        patch("devops_cli.ai.review.runner.is_dry_run", return_value=False),
        patch(
            "devops_cli.ai.review.runner._execute_review_segment_attempt",
            side_effect=_mock_attempt,
        ),
    ):
        results = _execute_review_segments(
            pages=pages,
            title="Parallel Segments Test",
            metadata={},
            build_prompt=_build_path_prompt,
            persona=persona,
            clients=clients,
            analysis_suffix="",
            analysis_system="System Prompt",
        )
        assert (
            len(results),
            max_active >= 2,
            "Review for segment 1/3" in results[0],
            results[1],
            "Review for segment 3/3" in results[2],
        ) == (3, True, True, "", True)


def test_execute_findings_validation_parallel_and_error_handling() -> None:
    """Verify _execute_findings_validation runs in parallel and isolates validation errors."""
    clients = MagicMock()
    clients.analysis._config.ollama_max_parallel = 2
    clients.analysis._config.ollama_urls = ["http://example.com:11434"]

    pages = ["diff --git a/one.py b/one.py", "diff --git a/two.py b/two.py"]
    res1 = ReviewResult(persona=Persona.DEVSECOPS, recommendation="APPROVE", findings=[])
    res2 = ReviewResult(persona=Persona.DEVSECOPS, recommendation="REQUEST CHANGES", findings=[])

    def _mock_val(index, page, parsed, total, all_pages, cl, metas, repo, suffix):
        if index == 2:
            raise RuntimeError("Validation crash")
        return (index, parsed)

    with (
        patch("devops_cli.ai.review.runner.is_dry_run", return_value=False),
        patch(
            "devops_cli.ai.review.runner._validate_single_segment_findings",
            side_effect=_mock_val,
        ),
    ):
        validated = _execute_findings_validation(
            pages=pages,
            segment_results=[res1, res2],
            clients=clients,
            analysis_suffix="",
        )
        assert (len(validated), validated[0], validated[1]) == (2, res1, None)


def test_run_persona_loop_parallel_and_error_handling() -> None:
    """Verify _run_persona_loop executes personas in parallel and isolates errors."""
    clients = MagicMock()
    clients.analysis._config.ollama_max_parallel = 2
    clients.analysis._config.ollama_urls = ["http://example.com:11434"]
    pages = ["diff content"]

    def _mock_run(pages, title, pd, cl, agents, build_p, prebuilt_metadata=None, session_dir=None):
        if pd.name == "qa":
            raise RuntimeError("QA Persona crashed")
        return f"Completed review for {pd.title}"

    with (
        patch("devops_cli.ai.review.runner.is_dry_run", return_value=False),
        patch("devops_cli.ai.review.runner._review_session_dir", return_value=None),
        patch("devops_cli.ai.review.runner._load_shared_metadata_for_pages", return_value={}),
        patch("devops_cli.ai.review.runner._run_review", side_effect=_mock_run),
        patch("devops_cli.ai.review.runner._print_review"),
    ):
        completed = _run_persona_loop(
            pages=pages,
            title="Persona Loop Test",
            build_prompt=_build_path_prompt,
            clients=clients,
            agents_md="",
            all_personas=True,
            persona=None,
        )
        completed_names = [pd.name for pd, _ in completed]
        assert ("qa" not in completed_names, "devsecops" in completed_names) == (
            True,
            True,
        )
