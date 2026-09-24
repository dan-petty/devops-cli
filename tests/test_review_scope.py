"""A review reads the code under review: the PR's own files, each file's own pages, every lockfile (#515)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

from devops_cli.ai.review.pipeline import _lockfiles_beside, _match_static_findings_to_files
from devops_cli.ai.review.runner import _materialize_pr_head, _run_orchestrator_review
from devops_cli.ai.review_schema import SavedFinding


class _FakeGitHub:
    def __init__(self, files: dict[str, str]) -> None:
        self.files = files
        self.fetched: list[tuple[str, str, str]] = []

    def get_file_at(self, repo: str, path: str, ref: str) -> str | None:
        self.fetched.append((repo, path, ref))
        return self.files.get(path)


def _pull(*changed: tuple[str, str]) -> Any:
    return SimpleNamespace(
        head=SimpleNamespace(sha="abc123", repo=SimpleNamespace(full_name="fork/app")),
        get_files=lambda: [
            SimpleNamespace(filename=name, status=status) for name, status in changed
        ],
    )


def test_a_pr_review_reads_the_pr_heads_files_and_conventions(tmp_path: Path) -> None:
    """Verify changed files are written at the head commit from the head repo, conventions too."""
    gh = _FakeGitHub(
        {
            "src/app.py": "print('head version')\n",
            "AGENTS.md": "# Conventions\n",
            ".devops/review.md": "# Review rules\n",
        }
    )
    pull = _pull(("src/app.py", "modified"), ("old.py", "removed"), ("../escape.py", "added"))

    written = _materialize_pr_head(gh, "base/app", pull, tmp_path)

    assert (
        written,
        (tmp_path / "src/app.py").read_text(encoding="utf-8"),
        (tmp_path / ".devops/review.md").exists(),
        (tmp_path / "old.py").exists(),
        (tmp_path.parent / "escape.py").exists(),
        {(repo, ref) for repo, _, ref in gh.fetched},
    ) == (3, "print('head version')\n", True, False, False, {("fork/app", "abc123")})


def test_the_pr_command_reviews_against_the_pr_head(tmp_path: Path) -> None:
    """Verify the review's target directory holds the PR head's files, not the local checkout."""
    from typer.testing import CliRunner

    from devops_cli.main import app

    seen: dict[str, Any] = {}

    def prepare(number: int, repo: Any, token: str, head_dir: Path) -> Any:
        (head_dir / "app.py").write_text("head\n", encoding="utf-8")
        return (["page"], "PR #7", "", MagicMock(), "base/app")

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
