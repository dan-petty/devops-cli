"""A repository, its `origin` and a clone of it, for the tests of the stage job (#2654).

`stage_repo` is real git in `tmp_path`: a bare `origin` whose path ends in `example/roadmap.git`,
so the clone's origin name reads `example/roadmap`, and a clone of it with the files a stage run
reads (`CONTEXT.md`, `openspec/config.yaml`, one spec and `src/devops_cli/sample.py`). The clone
commits as the identity `STAGE_EMAIL`.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.store import ItemField

STAGE_REPO = "example/roadmap"
STAGE_EMAIL = "1+devops-roadmap[bot]@users.noreply.github.com"
SAMPLE_SOURCE = "def keep(comments):\n    return comments[:-1]\n"


def run_git(cwd: Path, *args: str) -> str:
    """The output of `git <args>` in `cwd`."""
    done = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)  # nosec B603 B607
    return done.stdout.strip()


@dataclass(frozen=True)
class StageRepo:
    """The `origin` and the clone of a repository."""

    origin: Path
    clone: Path

    def git(self, *args: str) -> str:
        """`git <args>` in the clone."""
        return run_git(self.clone, *args)

    def origin_git(self, *args: str) -> str:
        """`git <args>` in `origin`."""
        return run_git(self.origin, *args)

    def push_branch(self, branch: str, *, email: str = "person@example.com") -> None:
        """Push one more commit by `email` to `branch` of `origin`, as another clone does; the
        branch starts at `main` when `origin` has none."""
        exists = bool(self.git("ls-remote", "--heads", "origin", branch))
        self.git("switch", "-q", "-c", branch, *([f"origin/{branch}"] if exists else []))
        name = f"{branch}-{email}".replace("/", "-")
        (self.clone / f"{name}.txt").write_text(name, encoding="utf-8")
        self.git("add", "-A")
        self.git("-c", f"user.email={email}", "commit", "-q", "-m", "work")
        self.git("push", "-q", "origin", branch)
        self.git("switch", "-q", "main")
        self.git("branch", "-q", "-D", branch)


@pytest.fixture
def stage_repo(tmp_path: Path) -> StageRepo:
    """A bare origin and a clone on `main`, with its remote branches fetched."""
    origin = tmp_path / "origin" / "example" / "roadmap.git"
    origin.mkdir(parents=True)
    run_git(origin, "init", "-q", "--bare", "-b", "main")
    clone = tmp_path / "clone"
    run_git(tmp_path, "clone", "-q", str(origin), str(clone))
    for key, value in (
        ("user.name", "devops-roadmap[bot]"),
        ("user.email", STAGE_EMAIL),
        ("commit.gpgsign", "false"),
    ):
        run_git(clone, "config", key, value)
    run_git(clone, "switch", "-q", "-c", "main")
    files = {
        "CONTEXT.md": "# Context\nThe job reads comments.\n",
        "openspec/config.yaml": "schema: spec-driven\n",
        "openspec/specs/roadmap-refine/spec.md": "# roadmap-refine Specification\n",
        "src/devops_cli/sample.py": SAMPLE_SOURCE,
    }
    for name, text in files.items():
        (clone / name).parent.mkdir(parents=True, exist_ok=True)
        (clone / name).write_text(text, encoding="utf-8")
    run_git(clone, "add", "-A")
    run_git(clone, "commit", "-q", "-m", "init")
    run_git(clone, "push", "-q", "origin", "main")
    run_git(origin, "symbolic-ref", "HEAD", "refs/heads/main")
    run_git(clone, "remote", "set-head", "origin", "--auto")
    return StageRepo(origin, clone)


def seed_stageable(
    store: InMemoryRoadmapStore,
    title: str = "fix(roadmap): the job drops a comment",
    *,
    body: str = "The job drops the last comment of a thread.",
) -> int:
    """A Ready P1 bug, opened by the owner, that the default filter names."""
    return store.seed_issue(
        title,
        body=body,
        labels=("type/bug",),
        fields={ItemField.STATUS: "Ready", ItemField.PRIORITY: "P1-High"},
    )


def write_big_file(repo: StageRepo, name: str = "src/devops_cli/big.py") -> None:
    """A Python file in the clone that is far over a budget of a few thousand tokens."""
    lines = [f"def function_{i}(value):\n    return value + {i}\n" for i in range(1500)]
    (repo.clone / name).write_text("\n".join(lines), encoding="utf-8")
