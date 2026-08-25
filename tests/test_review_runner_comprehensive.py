from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from devops_cli.ai.personas import PERSONAS, Persona
from devops_cli.ai.review.rendering import (
    _render_review_raw,
    _render_review_result,
)
from devops_cli.ai.review.runner import (
    ReviewClients,
    _build_path_prompt,
    _build_recompose_prompt,
    _build_segment_review_prompt,
    _collect_file_blocks,
    _collect_files,
    _get_reviews_base_dir,
    _git_repo_root,
    _is_allowed_review_boundary,
    _is_git_ignored,
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
)
from devops_cli.config.settings import Settings
from devops_cli.models.vulnerability import DependencySpec, NetworkReference


def test_rendering_helpers() -> None:
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
    _render_review_result(persona_def, res)
    _render_review_raw(persona_def, "## Raw review text")


def test_runner_file_and_repo_helpers(tmp_path: Path) -> None:
    st = Settings()
    st.repos.base_dir = tmp_path
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / ".git").mkdir()
    (repo_dir / "src").mkdir()
    f1 = repo_dir / "src" / "app.py"
    f1.write_text("print('hello')\n")
    (repo_dir / "AGENTS.md").write_text("# Agents Guidelines\n")

    assert _git_repo_root(f1) == repo_dir
    assert _is_allowed_review_boundary(f1, st) is True

    agents_content = _load_agents_md(repo_dir)
    assert "Agents Guidelines" in agents_content

    with patch("devops_cli.ai.review.runner.is_ignored_by_git", return_value=False):
        assert _is_git_ignored(f1, repo_dir) is False

    files = _collect_files(repo_dir / "src", "*.py")
    assert len(files) >= 1

    blocks = _collect_file_blocks(repo_dir / "src", "*.py")
    assert len(blocks) >= 1


def test_runner_persona_and_prompts() -> None:
    personas = _personas_to_run(all_personas=True, persona=None)
    assert len(personas) == 5

    p_devsecops = _personas_to_run(all_personas=False, persona=Persona.DEVSECOPS)
    assert p_devsecops == [PERSONAS[Persona.DEVSECOPS]]

    prompt = _build_path_prompt("print('hello')", "Agents context")
    assert "print('hello')" in prompt
    assert "Agents context" in prompt

    pd = PERSONAS[Persona.DEVSECOPS]
    seg_prompt = _build_segment_review_prompt(
        "diff block", "Title", 1, 2, {}, _build_path_prompt, pd
    )
    assert '"total_files": 2' in seg_prompt
    assert '"current_file_index": 1' in seg_prompt

    recompose_prompt = _build_recompose_prompt("Test Title", {}, ["response 1"], pd, [])
    prompt_lower = recompose_prompt.lower()
    assert "recompose" in prompt_lower or "consolidate" in prompt_lower or "review" in prompt_lower


def test_runner_session_persistence(tmp_path: Path) -> None:
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
    st = Settings()
    clients = _make_review_clients(st)
    assert isinstance(clients, ReviewClients)

    res_clients = _resolve_review_clients(st)
    assert res_clients is not None


def test_prepare_content_helpers(tmp_path: Path) -> None:
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
        b_pages, b_title, b_agents = _prepare_branch_content("feat/test", "main", Path("."))
        assert len(b_pages) >= 1
        assert "feat/test" in b_title

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
