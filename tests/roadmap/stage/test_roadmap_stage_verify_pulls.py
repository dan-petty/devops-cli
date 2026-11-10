"""The files of a named pull request at its merge commit (#3447).

The reader is tested on a real two-commit history, so the merge commit is the only place that holds
the text of the pull request. The quote tests then show that a finding which quotes a pull request
file returns the plan, and that the prompt names the new key.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from devops_cli.ai.context_budget import count_tokens
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.constants import (
    CONST_ROADMAP_STAGE_VERIFY_FILE_MAX_TOKENS,
    CONST_ROADMAP_STAGE_VERIFY_MAX_FILES,
)
from devops_cli.github.client import PullStatus
from devops_cli.roadmap.stage.stage_eval_cases import DefectType
from devops_cli.roadmap.stage.stage_verify import (
    Finding,
    VerificationInput,
    open_findings,
    returning,
)
from devops_cli.roadmap.stage.stage_verify_pulls import (
    PullRequestFiles,
    named_numbers,
    read_named_pulls,
)

PLAN = {
    "summary": "Stop the job dropping a comment",
    "why": "The job drops the last comment of a thread.",
    "groups": [
        {
            "title": "Keep the last comment",
            "reads": ["src/a.py"],
            "changes": ["src/a.py"],
        }
    ],
}


class FakeReads:
    """A GitHub client that answers the status of each pull request, and no other read."""

    def __init__(self, statuses: dict[int, PullStatus]) -> None:
        self._statuses = statuses
        self.read: list[int] = []

    def get_pull_status(self, repo: str, number: int) -> PullStatus:
        self.read.append(number)
        return self._statuses[number]


def _git(cwd: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)
    return done.stdout.strip()


@pytest.fixture
def pull_checkout(tmp_path: Path) -> tuple[Path, str, str]:
    """A checkout with a base commit and a merge commit, and the base and the merge sha."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    for key, value in (("user.email", "ci@example.com"), ("user.name", "CI")):
        _git(root, "config", key, value)
    _git(root, "config", "commit.gpgsign", "false")
    (root / "base.txt").write_text("the base text\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    base = _git(root, "rev-parse", "HEAD")
    _git(root, "checkout", "-q", "-b", "feature")
    (root / "plan.txt").write_text("the pull request text\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "feature")
    _git(root, "checkout", "-q", "main")
    _git(root, "merge", "-q", "--no-ff", "feature", "-m", "merge")
    return root, base, _git(root, "rev-parse", "HEAD")


def _reads(merge: str, number: int = 3378) -> FakeReads:
    return FakeReads({number: PullStatus(state="closed", merged=True, merge_commit_sha=merge)})


def test_a_named_pull_request_is_read_at_its_merge_commit(
    pull_checkout: tuple[Path, str, str],
) -> None:
    root, _, merge = pull_checkout

    found = read_named_pulls(
        root,
        named_numbers("The claim of pull request #3378 is wrong."),
        reads=lambda: _reads(merge),
        repo="example/repo",
    )

    assert [(pull.number, pull.merge_commit) for pull in found] == [(3378, merge)]
    assert found[0].files == {"plan.txt": "the pull request text\n"}


def test_only_the_pull_request_and_pr_phrases_name_a_number() -> None:
    text = "See PR #12, pull request #13 and #14, then Pull Request #12 again."

    assert named_numbers(text) == (12, 13)


def test_a_pull_request_with_no_merge_commit_adds_no_entry(
    pull_checkout: tuple[Path, str, str],
) -> None:
    root, _, _ = pull_checkout
    reads = FakeReads({12: PullStatus(state="open", draft=True)})

    assert read_named_pulls(root, (12,), reads=lambda: reads, repo="example/repo") == ()


def test_a_large_pull_request_is_bounded(pull_checkout: tuple[Path, str, str]) -> None:
    root, _, merge = pull_checkout
    _git(root, "checkout", "-q", "-b", "large")
    for number in range(CONST_ROADMAP_STAGE_VERIFY_MAX_FILES + 5):
        (root / f"file{number}.txt").write_text(
            " ".join(f"word{n}" for n in range(CONST_ROADMAP_STAGE_VERIFY_FILE_MAX_TOKENS * 2)),
            encoding="utf-8",
        )
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "large")
    _git(root, "checkout", "-q", "main")
    _git(root, "merge", "-q", "--no-ff", "large", "-m", "merge large")
    merge = _git(root, "rev-parse", "HEAD")

    found = read_named_pulls(root, (12,), reads=lambda: _reads(merge, 12), repo="example/repo")

    assert len(found) == 1
    assert len(found[0].files) == CONST_ROADMAP_STAGE_VERIFY_MAX_FILES
    for text in found[0].files.values():
        assert count_tokens(text) <= CONST_ROADMAP_STAGE_VERIFY_FILE_MAX_TOKENS


def test_a_quote_from_a_pull_request_file_returns_the_plan() -> None:
    pull = PullRequestFiles(
        3378,
        "abc123",
        {"openspec/changes/3372-a-move/tasks.md": "1.1 Add the check to `stage_move.py`."},
    )
    given = VerificationInput.of(
        number=7,
        title="fix(roadmap): the job reads the plan of a pull request",
        body="The plan of #3372 says that pull request #3378 chose a move.",
        plan=PLAN,
        source=Path("/nonexistent"),
        pull_requests=(pull,),
    )
    finding = Finding(
        type=DefectType.FALSE_PREMISE,
        where="feasibility",
        problem="The named pull request holds no move group.",
        quote="Add the check to `stage_move.py`.",
    )

    assert returning([finding], given) == [finding]
    assert open_findings([finding], given) == [finding]


def test_the_hash_3410_claim_is_a_false_premise() -> None:
    """The claim of #3410 names a literal and a move, and the recorded #3378 plan holds no move
    group."""
    plan_text = (
        "## Tasks\n\n"
        "## 1. Add the prefix check\n\n"
        "- [ ] 1.1 Add `devops_cli.roadmap.stage_move` to the check\n"
        "  - Verification: `! git grep -n -F devops_cli.roadmap.stage src/ tests/`\n"
    )
    pull = PullRequestFiles(
        3378,
        "abc123",
        {"openspec/changes/3372-a-move/tasks.md": plan_text},
    )
    given = VerificationInput.of(
        number=3410,
        title="fix(roadmap): the stage job checks the move prefix",
        body=(
            "The plan of #3372 in pull request #3378 chose "
            "`! git grep -n -F devops_cli.roadmap.stage src/ tests/` as the whole-prefix check "
            "for a move of the `stage*` modules."
        ),
        plan=PLAN,
        source=Path("/nonexistent"),
        pull_requests=(pull,),
    )
    finding = Finding(
        type=DefectType.FALSE_PREMISE,
        where="feasibility",
        problem="Pull request #3378 holds no movement of the modules, only the literal check.",
        quote="`! git grep -n -F devops_cli.roadmap.stage src/ tests/`",
    )

    assert finding.quote in plan_text
    assert returning([finding], given) == [finding]
    assert open_findings([finding], given) == [finding]


def test_the_verification_prompt_names_the_named_pull_requests() -> None:
    prompt = load_task_prompt("roadmap_stage_verify.md")

    assert "`pull_requests`" in prompt
    assert "`merge_commit`" in prompt
    assert "`files`" in prompt
