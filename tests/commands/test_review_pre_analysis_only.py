"""`devops review branch --pre-analysis-only` analyzes the changed files and says what it does
(#1919).

A run that calls no model said `via LLM server`, and it counted its files as pages.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

from devops_cli.ai.analyze import load_cached_analysis
from tests.support.fakes.git import GitFake
from tests.support.fakes.process import ProcessAnswer, ProcessCall

_CHANGED = ["src/app.sh", "src/util.sh"]


def _repository(root: Path) -> Path:
    """A repository of twelve shell scripts whose branch `feature` changes `_CHANGED`. Shell
    scripts reach no scanner when the static scan is off."""
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / ".git").mkdir(parents=True, exist_ok=True)
    (root / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    names = ["app", "util", *(f"tool{index}" for index in range(10))]
    for name in names:
        (root / "src" / f"{name}.sh").write_text(f"echo {name}\n", encoding="utf-8")
    return root


def _handle_git_worktree(argv: list[str], repo: Path) -> ProcessAnswer:
    if "add" in argv:
        dest = Path(argv[argv.index("add") + 2])
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(repo, dest, dirs_exist_ok=True)
        for name in _CHANGED:
            (dest / name).write_text(
                (repo / name).read_text(encoding="utf-8") + "exit 0\n",
                encoding="utf-8",
            )
        return ProcessAnswer(returncode=0, stdout="")
    return ProcessAnswer(returncode=0, stdout="")


def _setup_pre_analysis_git_fake(git_fake: GitFake, repo: Path) -> None:
    diff_text = (
        "diff --git a/src/app.sh b/src/app.sh\n"
        "--- a/src/app.sh\n"
        "+++ b/src/app.sh\n"
        "@@ -1 +1,2 @@\n"
        " echo app\n"
        "+exit 0\n"
        "diff --git a/src/util.sh b/src/util.sh\n"
        "--- a/src/util.sh\n"
        "+++ b/src/util.sh\n"
        "@@ -1 +1,2 @@\n"
        " echo util\n"
        "+exit 0\n"
    )

    def _answer(call: ProcessCall) -> ProcessAnswer:
        argv = call.argv or []
        if "rev-parse" in argv:
            if "--show-toplevel" in argv:
                return ProcessAnswer(returncode=0, stdout=f"{repo}\n")
            if "--abbrev-ref" in argv:
                return ProcessAnswer(returncode=0, stdout="main\n")
            return ProcessAnswer(
                returncode=0,
                stdout="2222222222222222222222222222222222222222\n",
            )
        if "merge-base" in argv:
            return ProcessAnswer(returncode=0, stdout="1111111111111111111111111111111111111111\n")
        if "log" in argv:
            return ProcessAnswer(returncode=0, stdout="2222222222222222222222222222222222222222\n")
        if "diff" in argv:
            if "--name-status" in argv:
                return ProcessAnswer(returncode=0, stdout="M\tsrc/app.sh\nM\tsrc/util.sh\n")
            return ProcessAnswer(returncode=0, stdout=diff_text)
        if "worktree" in argv:
            return _handle_git_worktree(argv, repo)
        return ProcessAnswer(returncode=0, stdout="")

    git_fake.answer(lambda call: True, _answer)


def test_a_pre_analysis_only_branch_review_analyzes_the_changed_files_with_no_model(
    tmp_path: Path, cli: Callable[..., Any], git_fake: GitFake
) -> None:
    """Verify the review analyzes the two changed files of twelve, says that it uses no model,
    and names no pages. Its profile line does not end in the separator of a stage list that is
    empty because no stage took a second."""
    repo = _repository(tmp_path / "repo")
    _setup_pre_analysis_git_fake(git_fake, repo)

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
