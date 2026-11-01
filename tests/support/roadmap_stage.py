"""A repository, its `origin` and a clone of it, for the tests of the stage job (#2654).

`stage_repo` is real git in `tmp_path`: a bare `origin` whose path ends in `example/roadmap.git`,
so the clone's origin name reads `example/roadmap`, and a clone of it with the files a stage run
reads (`CONTEXT.md`, `openspec/config.yaml`, one spec and `src/devops_cli/sample.py`). The clone
commits as the identity `STAGE_EMAIL`.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import pytest

from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.stage_change import StageGroup
from devops_cli.roadmap.store import ItemField
from tests.support.builders import make_stage_proposal

STAGE_REPO = "example/roadmap"
STAGE_NAME = "devops-roadmap[bot]"
STAGE_EMAIL = "1+devops-roadmap[bot]@users.noreply.github.com"
# What `openspec validate <change> --strict --json` prints for a valid change.
VALID_REPORT = json.dumps({"items": [{"id": "x", "valid": True, "issues": []}]})
SAMPLE_SOURCE = "def keep(comments):\n    return comments[:-1]\n"


def run_git(cwd: Path, *args: str) -> str:
    """The output of `git <args>` in `cwd`."""
    done = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)
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

    def track(self, files: Mapping[str, str]) -> None:
        """Write `files` (text by path), commit them to `main` and push, so the checkout tracks
        them at its HEAD, as the stage job reads the files of the commit it plans."""
        for name, text in files.items():
            (self.clone / name).parent.mkdir(parents=True, exist_ok=True)
            (self.clone / name).write_text(text, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "track files")
        self.git("push", "-q", "origin", "main")

    def push_branch(self, branch: str, *, author: str = "Person") -> None:
        """Push one more commit by `author` to `branch` of `origin`, as another clone does; the
        branch starts at `main` when `origin` has none."""
        exists = bool(self.git("ls-remote", "--heads", "origin", branch))
        self.git("switch", "-q", "-c", branch, *([f"origin/{branch}"] if exists else []))
        name = f"{branch}-{author}".replace("/", "-").replace(" ", "-")
        (self.clone / f"{name}.txt").write_text(name, encoding="utf-8")
        self.git("add", "-A")
        self.git("-c", f"user.name={author}", "commit", "-q", "-m", "work")
        self.git("push", "-q", "origin", branch)
        self.git("switch", "-q", "main")
        self.git("branch", "-q", "-D", branch)

    def stray_branch(self, branch: str, *, own_commit: bool = False) -> None:
        """Make the local `branch` with no worktree, at `main` or with one commit that `origin`
        lacks, as a job that died before its cleanup leaves it (#2724)."""
        self.git("branch", "-q", branch)
        if own_commit:
            self.git("switch", "-q", branch)
            (self.clone / "stray.txt").write_text("stray\n", encoding="utf-8")
            self.git("add", "-A")
            self.git("commit", "-q", "-m", "stray work")
            self.git("switch", "-q", "main")


@pytest.fixture
def stage_repo(tmp_path: Path) -> StageRepo:
    """A bare origin and a clone on `main`, with its remote branches fetched."""
    origin = tmp_path / "origin" / "example" / "roadmap.git"
    origin.mkdir(parents=True)
    run_git(origin, "init", "-q", "--bare", "-b", "main")
    clone = tmp_path / "clone"
    run_git(tmp_path, "clone", "-q", str(origin), str(clone))
    for key, value in (
        ("user.name", STAGE_NAME),
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


# The update that makes a heavy group light: it reads no file and its tasks name none.
NO_FILES = {"reads": [], "implementation": "Keep the last comment"}


def heavy_group(repo: StageRepo, *, files: int = 4) -> StageGroup:
    """A task group that reads `files` large Python files of the clone and names each one in its
    implementation task, as the step finds a file to read. The step packs each file to the file
    cap, so the group measures about `files` times that cap: far over a budget of a few thousand
    tokens when `files` is 4."""
    names = [f"src/devops_cli/big_{i}.py" for i in range(files)]
    lines = [f"def function_{i}(value):\n    return value + {i}\n" for i in range(1500)]
    repo.track({name: "\n".join(lines) for name in names})
    spans = ", ".join(f"`{name}`" for name in names)
    return (
        make_stage_proposal()
        .groups[0]
        .model_copy(update={"reads": names, "implementation": f"Keep the last comment in {spans}"})
    )


def validate_args(change: str) -> tuple[str, ...]:
    """The arguments of the validation the stage job runs on `change`."""
    return ("validate", change, "--strict", "--json")


def validation_report(*issues: tuple[str, str], valid: bool = True) -> str:
    """What `openspec validate --json` prints for a change with these (level, message) issues."""
    found = [{"level": level, "path": "cap/spec.md", "message": text} for level, text in issues]
    return json.dumps({"items": [{"id": "x", "valid": valid, "issues": found}]})
