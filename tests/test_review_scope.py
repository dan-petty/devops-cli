"""A review reads the code under review: the PR's own files, each file's own pages, every lockfile
(#515), and the PR's base at its merge base (#593)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
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

_MERGE_BASE = "merge789"


class _FakeGitHub:
    """GitHub as a PR review reads it: file texts by (path, ref), the merge base of the pull
    request's base and head, and the pull request itself. Every read is logged."""

    def __init__(self, files: dict[tuple[str, str], str], pull: Any = None, diff: str = "") -> None:
        self.files = files
        self.pull = pull
        self.diff = diff
        self.fetched: list[tuple[str, str, str]] = []
        self.compared: list[tuple[str, str, str]] = []

    def get_file_at(self, repo: str, path: str, ref: str) -> str | None:
        self.fetched.append((repo, path, ref))
        return self.files.get((path, ref))

    def get_merge_base(self, repo: str, base: str, head: str) -> str:
        self.compared.append((repo, base, head))
        return _MERGE_BASE

    def get_pull(self, repo: str, number: int) -> Any:
        return self.pull

    def get_pr_diff(self, repo: str, number: int) -> str:
        return self.diff


def _pull(*changed: tuple[str, str], renamed_from: dict[str, str] | None = None) -> Any:
    old_paths = renamed_from or {}
    return SimpleNamespace(
        title="Change the app",
        head=SimpleNamespace(sha="abc123", repo=SimpleNamespace(full_name="fork/app")),
        base=SimpleNamespace(sha="base456", ref="main", repo=SimpleNamespace(full_name="base/app")),
        get_files=lambda: [
            SimpleNamespace(filename=name, status=status, previous_filename=old_paths.get(name))
            for name, status in changed
        ],
    )


def test_a_pr_review_reads_the_pr_heads_files_and_conventions(tmp_path: Path) -> None:
    """Verify changed files are written from head repo, and conventions are safely loaded from base (#658)."""
    gh = _FakeGitHub(
        {
            ("src/app.py", "abc123"): "print('head version')\n",
            ("AGENTS.md", "base456"): "# Conventions\n",
            (".devops/review.md", "base456"): "# Review rules\n",
        }
    )
    pull = _pull(("src/app.py", "modified"), ("old.py", "removed"), ("../escape.py", "added"))

    written = _materialize_pr_head(gh, "base/app", pull, tmp_path, pull.get_files())

    head_fetches = {(repo, path, ref) for repo, path, ref in gh.fetched if repo == "fork/app"}
    base_fetches = {(repo, path, ref) for repo, path, ref in gh.fetched if repo == "base/app"}

    assert (
        written,
        (tmp_path / "src/app.py").read_text(encoding="utf-8"),
        (tmp_path / ".devops/review.md").exists(),
        (tmp_path / "old.py").exists(),
        (tmp_path.parent / "escape.py").exists(),
        head_fetches,
        ("base/app", ".devops/review.md", "base456") in base_fetches,
    ) == (
        3,
        "print('head version')\n",
        True,
        False,
        False,
        {("fork/app", "src/app.py", "abc123")},
        True,
    )


def test_the_pr_command_reviews_against_the_pr_head(tmp_path: Path) -> None:
    """Verify the review's target directory holds the PR head's files, not the local checkout."""
    from typer.testing import CliRunner

    from devops_cli.main import app

    seen: dict[str, Any] = {}

    def prepare(number: int, repo: Any, token: str, head_dir: Path) -> Any:
        (head_dir / "app.py").write_text("head\n", encoding="utf-8")
        return (["page"], "PR #7", "", MagicMock(), "base/app", None)

    def run(*args: Any, **kwargs: Any) -> list[Any]:
        target = kwargs["target_dir"]
        seen["content"] = (target / "app.py").read_text(encoding="utf-8")
        seen["local"] = target.resolve() == Path.cwd().resolve()
        return []

    with (
        patch("devops_cli.config.settings.get_github_token", return_value="t"),
        patch("devops_cli.commands.review._make_review_clients", return_value=MagicMock()),
        patch("devops_cli.commands.review._prepare_pr_content", side_effect=prepare),
        patch("devops_cli.commands.review._execute_review_workflow", side_effect=run),
    ):
        result = CliRunner().invoke(app, ["review", "pr", "7", "--repo", "base/app"])

    assert (result.exit_code, seen) == (0, {"content": "head\n", "local": False})


def test_a_pr_review_reads_the_base_at_the_merge_base_and_records_the_delta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a PR review reads each modified or renamed Python file from the base repository at
    the merge base, a renamed one at its old path, and records the delta in the session (#593).

    `pull.base.sha` is the base branch's tip: read there, symbols added on the base since the
    branch point would count as removed by the PR.
    """
    monkeypatch.setenv("DEVOPS_CLI_DATA_ANALYSIS_DIR", str(tmp_path / "analysis"))
    pull = _pull(
        ("mod.py", "modified"),
        ("new_name.py", "renamed"),
        ("added.py", "added"),
        ("gone.py", "removed"),
        renamed_from={"new_name.py": "old_name.py"},
    )
    gh = _FakeGitHub(
        {
            ("mod.py", "abc123"): "def keep():\n    return 1\n",
            (
                "new_name.py",
                "abc123",
            ): "def moved():\n    return 2\n\n\ndef fresh():\n    return 3\n",
            ("added.py", "abc123"): "def brand_new():\n    return 4\n",
            (
                "mod.py",
                _MERGE_BASE,
            ): "def legacy_helper():\n    return 0\n\n\ndef keep():\n    return 1\n",
            (
                "old_name.py",
                _MERGE_BASE,
            ): "def moved():\n    return 2\n\n\ndef dropped():\n    return 5\n",
            (
                "mod.py",
                "base456",
            ): "def main_only():\n    return 6\n\n\ndef keep():\n    return 1\n",
        },
        pull=pull,
        diff="diff --git a/mod.py b/mod.py\n@@ -1,5 +1,2 @@\n-def legacy_helper():\n",
    )
    head_dir = tmp_path / "head"
    head_dir.mkdir()

    with patch("devops_cli.github.client.GitHubClient", return_value=gh):
        *_, base_revision = _prepare_pr_content(7, "base/app", "token", head_dir=head_dir)
    orchestrator = ReviewPipelineOrchestrator(
        session_id="pr-7",
        llm_client=MagicMock(),
        session_dir=tmp_path / "session",
        concurrency=1,
        target_dir=tmp_path,
    )
    metadata = orchestrator.run_pre_analysis_refresh(
        target_dir=head_dir, target_type="pr", target_ref="7", base_revision=base_revision
    )

    source_base_reads = sorted(
        (path, ref) for repo, path, ref in gh.fetched if repo == "base/app" and path.endswith(".py")
    )
    deltas = {
        path: (m.symbols_added, m.symbols_removed, m.symbols_retained)
        for path, m in metadata.items()
        if path.endswith(".py")
    }
    assert (gh.compared, source_base_reads, deltas) == (
        [("base/app", "base456", "abc123")],
        [("mod.py", _MERGE_BASE), ("old_name.py", _MERGE_BASE)],
        {
            "mod.py": ([], ["legacy_helper"], ["keep"]),
            "new_name.py": (["fresh"], ["dropped"], ["moved"]),
            "added.py": (["brand_new"], [], []),
        },
    )


def test_each_file_is_reviewed_with_its_own_pages_only() -> None:
    """Verify `a.py` is not given the pages of `data.py`, whose name contains it."""
    orchestrator = MagicMock()
    orchestrator.init_per_file_payloads.return_value = []
    orchestrator.generate_consolidated_report.return_value = ({}, "report")
    pages = ["### File: data.py\n```python\nx = 1\n```", "### File: a.py\n```python\ny = 2\n```"]

    _run_orchestrator_review(orchestrator, ["a.py", "data.py"], {}, None, pages, ["qa"], None)

    diff_map = orchestrator.execute_multi_persona_review.call_args.kwargs["diff_text_by_file"]
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
