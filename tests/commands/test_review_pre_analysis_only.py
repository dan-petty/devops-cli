"""`devops review branch --pre-analysis-only` analyzes the changed files and says what it does
(#1919).

A run that calls no model said `via LLM server`, and it counted its files as pages.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from devops_cli.ai.analyze import load_cached_analysis

_CHANGED = ["src/app.sh", "src/util.sh"]


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _repository(root: Path) -> Path:
    """A repository of twelve shell scripts whose branch `feature` changes `_CHANGED`. Shell
    scripts reach no scanner when the static scan is off."""
    (root / "src").mkdir(parents=True)
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.name", "Test Runner")
    _git(root, "config", "user.email", "runner@example.com")
    _git(root, "config", "commit.gpgsign", "false")
    names = ["app", "util", *(f"tool{index}" for index in range(10))]
    for name in names:
        (root / "src" / f"{name}.sh").write_text(f"echo {name}\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "base")
    _git(root, "checkout", "-b", "feature")
    for name in _CHANGED:
        (root / name).write_text((root / name).read_text(encoding="utf-8") + "exit 0\n", "utf-8")
    _git(root, "commit", "-am", "change two scripts")
    _git(root, "checkout", "main")
    return root


def test_a_pre_analysis_only_branch_review_analyzes_the_changed_files_with_no_model(
    tmp_path: Path, cli: Callable[..., Any]
) -> None:
    """Verify the review analyzes the two changed files of twelve, says that it uses no model,
    and names no pages. Its profile line does not end in the separator of a stage list that is
    empty because no stage took a second."""
    repo = _repository(tmp_path / "repo")

    result = cli(
        "review", "branch", "feature", "--base", "main", "--repo", str(repo), "--pre-analysis-only"
    )

    lines = [line.strip() for line in result.output.splitlines()]
    cached = load_cached_analysis(repo)
    assert (
        result.exit_code,
        [line.split("'")[2] for line in lines if line.startswith("Initializing review pipeline")],
        [line for line in lines if "Pre-analysis metadata for" in line],
        [line for line in lines if "pages" in line],
        [line.endswith(";") for line in lines if line.startswith("Profile:")],
        sorted(f.path for f in cached.files) if cached else None,
    ) == (
        0,
        [" for 2 file(s) without a model..."],
        ["✓ Pre-analysis metadata for 2 file(s): 2 analyzed, 0 reused from the cache"],
        [],
        [False],
        _CHANGED,
    )
