"""What the tests of `devops roadmap implement` share (#2664): a checkout with a change folder,
the item it belongs to, the process edge, and the calls of an agent that completes group 1.

The checkout is a git repository in `tmp_path`. Git runs for real on it; every other program is
answered by `process_fake`.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.store import ItemField
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake

REPO = "example/roadmap"
WINDOW = 128000

TASKS = """\
# Tasks

## 1. The first group

- [ ] Add the failing test `tests/test_sample.py` for `src/sample.py`
  - Verification: `uv run devops ci test tests/test_sample.py`
- [ ] Add `shout` to `src/sample.py`
  - Verification: `uv run devops ci test tests/test_sample.py` and `uv run devops docs check`

## 2. The second group

- [x] Document the function in `docs/SAMPLE.md`
  - Verification: `uv run devops docs check`

## Workflow follow-up

- A plain bullet with `src/other.py` in it.
"""

BODY = """\
## Problem or Motivation

The sample cannot shout.

## Proposed Solution & Architectural Design

A long design that the step does not need.

## Acceptance criteria

- `shout("a")` returns `A!`.

## Target Subsystem

Nothing else.
"""

SAMPLE = '''\
"""A sample module."""


def hello(name: str) -> str:
    """Greet `name`."""
    return f"hello {name}"
'''


def git(cwd: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)
    return done.stdout.strip()


def make_checkout(root: Path, tasks: str = TASKS) -> Path:
    """A git checkout whose one commit holds change `1-sample-change` and two source files."""
    checkout = root / "checkout"
    change = checkout / "openspec" / "changes" / "1-sample-change"
    change.mkdir(parents=True)
    (checkout / "src").mkdir()
    (checkout / "docs").mkdir()
    (checkout / "tests").mkdir()
    (checkout / "tests" / "conftest.py").write_text('"""The tests."""\n', encoding="utf-8")
    git(checkout, "init", "-q", "-b", "main")
    for key, value in (("user.email", "ci@example.com"), ("user.name", "CI")):
        git(checkout, "config", key, value)
    git(checkout, "config", "commit.gpgsign", "false")
    (change / "proposal.md").write_text("# Proposal\n\nWhy the sample shouts.\n", encoding="utf-8")
    (change / "design.md").write_text("# Design\n\nShout in capitals.\n", encoding="utf-8")
    (change / "tasks.md").write_text(tasks, encoding="utf-8")
    (checkout / "src" / "sample.py").write_text(SAMPLE, encoding="utf-8")
    (checkout / "src" / "other.py").write_text("OTHER = 1\n", encoding="utf-8")
    (checkout / "docs" / "SAMPLE.md").write_text("The sample.\n", encoding="utf-8")
    git(checkout, "add", "-A")
    git(checkout, "commit", "-q", "-m", "init")
    return checkout


@pytest.fixture
def implement_store() -> InMemoryRoadmapStore:
    """A private roadmap whose item 1 is the sample item."""
    roadmap = InMemoryRoadmapStore(repo=REPO, is_private=True)
    roadmap.seed_issue(
        "Make the sample shout",
        body=BODY,
        fields={ItemField.STATUS: "Ready", ItemField.PRIORITY: "P1-High"},
    )
    return roadmap


@pytest.fixture
def implement_checkout(tmp_path: Path) -> Path:
    return make_checkout(tmp_path)


TASKS_PATH = "openspec/changes/1-sample-change/tasks.md"
TICKED = TASKS.replace("- [ ] Add", "- [x] Add")
LATER_OPEN = TASKS.replace("- [x] Document", "- [ ] Document")
EVERY_TICK = TICKED.replace("- [ ] Document", "- [x] Document")
TEST_BODY = "def test_shout() -> None:\n    assert True\n"
SHOUT_CODE = SAMPLE + '\n\ndef shout(text: str) -> str:\n    return text.upper() + "!"\n'
CHECK = "uv run devops ci test tests/test_sample.py"
DOCS = "uv run devops docs check"


def write_call(path: str, content: str) -> tuple[str, dict[str, Any]]:
    return "write_file", {"path": path, "content": content}


def the_whole_group() -> tuple[tuple[str, dict[str, Any]], ...]:
    """The calls of an agent that writes the test and the code, and ticks the group's tasks."""
    return (
        write_call("tests/test_sample.py", TEST_BODY),
        write_call("src/sample.py", SHOUT_CODE),
        write_call(TASKS_PATH, TICKED),
    )


def git_for_real(call: ProcessCall) -> subprocess.CompletedProcess[str]:
    """Run the call for real. Output that is not UTF-8 is decoded with `errors="replace"`, as the
    real process runner decodes it, so that the diff of a file of any bytes reads the same."""
    return subprocess.run(
        call.argv, cwd=call.cwd, capture_output=True, text=True, errors="replace", check=False
    )


@pytest.fixture
def implement_programs(process_fake: ProcessFake) -> ProcessFake:
    """The process edge: git runs for real, and every other program exits 0 unless a test says
    otherwise."""
    process_fake.answer("git", ProcessAnswer(side_effect=git_for_real))
    return process_fake


PREVIEW = ("--preview-features", "malware-check,check-command")


def command_text(call: ProcessCall) -> str:
    """The command line of a call, without the preview flags that the runner adds to uv."""
    return " ".join(word for word in call.argv if word not in PREVIEW)


def programs_run(fake: ProcessFake, program: str) -> list[str]:
    return [command_text(call) for call in fake.calls if call.argv[0] == program]


def is_clean_at(checkout: Path, head: str) -> bool:
    return (git(checkout, "rev-parse", "HEAD"), git(checkout, "status", "--porcelain")) == (
        head,
        "",
    )


def tool_reads(word: str, report: str) -> Callable[[ProcessCall], subprocess.CompletedProcess[str]]:
    """A static tool that fails when a file after `--` holds `word`, and prints `report`."""

    def answer(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        assert call.cwd is not None
        names = call.argv[call.argv.index("--") + 1 :]
        failed = any(word in (call.cwd / name).read_text(encoding="utf-8") for name in names)
        return subprocess.CompletedProcess(
            call.argv, 1 if failed else 0, stdout=f"{report}\n" if failed else "", stderr=""
        )

    return answer
