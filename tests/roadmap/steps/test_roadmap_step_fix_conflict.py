"""Tests for the roadmap step `fix-conflict` (#5019).

Verifies:
- Dry-run sees 0 requests
- A person pull request is refused
- A person commit past the default branch fails a confirmed round
- An item with an owner label or human claim is refused
- Conflict on a release path stops with class conflict
- Archive-only conflict ends with clean push and 0 model requests
- Soft and hard caps hold
- Strict validation runs before push
- Without --confirm the step runs no code of the pull request and writes nothing
- A confirmed round pushes from a new repository to the repository on GitHub
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.config.commands import BIN_OPENSPEC, BIN_UV
from devops_cli.config.constants import (
    CONST_CHANGELOG_FILENAME,
    CONST_GIT_CLI,
    CONST_GIT_MAIN_BRANCH,
)
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions.git import GitOperationError
from devops_cli.github.client import PullStatus
from devops_cli.roadmap.phases import checkout as phases_checkout
from devops_cli.roadmap.phases.files import RunFolders
from devops_cli.roadmap.steps import fix_conflict, fix_conflict_phases
from devops_cli.roadmap.steps.fix_conflict import (
    FixConflictReport,
    FixConflictResult,
    check_merge_tree_conflict,
    dry_run_fix_conflict,
    is_archive_path,
    is_generated_docs_path,
    is_lockfile_path,
    is_release_path,
    run_fix_conflict,
)
from devops_cli.roadmap.stores.store import FixConflictRecordKey
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_implement import STEPS_DECLARATION, STEPS_FILE
from tests.support.run_folders import read_only_run

if TYPE_CHECKING:
    pass

pytestmark = pytest.mark.usefixtures("keyring_store")

REPO = "example/project"
BOT_USER = "devops-cli-service[bot]"
BOT_EMAIL = "bot@example.com"


@pytest.fixture(autouse=True)
def _app_bot(config: Callable[..., Path]) -> None:
    """The App whose bot is `BOT_USER`: `clone_branch` takes a branch whose every commit past
    main the bot wrote (#6703)."""
    config(service={"github_app": {"slug": BOT_USER.removesuffix("[bot]")}})


def _fake_github(
    monkeypatch: pytest.MonkeyPatch, status: PullStatus, origin: Path
) -> list[PullStatus]:
    """GitHub gives `status` and the identity of the bot, and the repository on GitHub is the bare
    repository `origin`, which `prepare` clones and `publish` pushes to. The merged plan names no
    workflow file. GitHub gives the last status of the list, which a test can extend."""
    statuses = [status]

    class FakeClient:
        def get_pull_status(self, repo: str, number: int) -> PullStatus:
            return statuses[-1]

    class FakeSession:
        client = FakeClient()
        login = BOT_USER
        commit_email = BOT_EMAIL

    for module in (fix_conflict, fix_conflict_phases, phases_checkout):
        monkeypatch.setattr(module, "get_github_session", lambda: FakeSession())
    monkeypatch.setattr(fix_conflict_phases, "CONST_GITHUB_CLONE_URL", str(origin))
    monkeypatch.setattr(fix_conflict_phases, "merged_workflows", lambda *_: ())
    return statuses


BRANCH = "feat/42-fix-conflict"


def _git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(
        [CONST_GIT_CLI, "-C", str(cwd), *args], capture_output=True, text=True, check=True
    )
    return proc.stdout.strip()


def test_dry_run_sees_zero_requests() -> None:
    """A dry-run test sees 0 requests."""
    reads, writes = dry_run_fix_conflict(REPO, 42)
    assert reads == ()
    assert writes == ()


def test_is_path_helpers() -> None:
    assert is_release_path(CONST_CHANGELOG_FILENAME)
    assert is_release_path(".release-please-manifest.json")
    assert is_release_path("release-please-config.json")
    assert is_release_path("pyproject.toml", '+version = "1.2.0"')
    assert not is_release_path("pyproject.toml", '+dependencies = ["foo>=1.2"]')
    assert not is_release_path("uv.lock", '+version = "1.2.0"')
    assert not is_release_path("src/module.py")

    assert is_archive_path("openspec/specs/capability/spec.md")
    assert is_archive_path("openspec/changes/archive/2026-11-16-42-slug/tasks.md")
    assert not is_archive_path("openspec/changes/42-slug/tasks.md")

    assert is_generated_docs_path("docs/CLI_REFERENCE.md")
    assert is_generated_docs_path("docs/commands/roadmap.md")
    assert not is_generated_docs_path("docs/DESIGN.md")

    assert is_lockfile_path("uv.lock")
    assert not is_lockfile_path("package-lock.json")


def test_person_pull_request_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """A person's pull request is refused."""
    store = InMemoryRoadmapStore(repo=REPO)
    human_status = PullStatus.model_validate(
        {
            "state": "open",
            "draft": False,
            "head": {"ref": BRANCH, "sha": "111111"},
            "base": {"ref": CONST_GIT_MAIN_BRANCH},
            "user": {"login": "human-developer"},
            "labels": [],
        }
    )

    class FakeClient:
        def get_pull_status(self, repo: str, pull: int) -> PullStatus:
            return human_status

    class FakeSession:
        client = FakeClient()

    monkeypatch.setattr(fix_conflict, "get_github_session", lambda: FakeSession())

    report = run_fix_conflict(store, REPO, 42)
    assert report.result == FixConflictResult.REFUSED
    assert "not a bot" in report.reason


def test_owner_label_or_claim_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """An item or PR holding an owner label is refused."""
    store = InMemoryRoadmapStore(repo=REPO)
    num = store.seed_issue(
        title="feat: something",
        labels=("status/in-progress", "priority/p2-medium", "owner/human"),
    )
    bot_status = PullStatus.model_validate(
        {
            "state": "open",
            "draft": False,
            "head": {"ref": f"feat/{num}-fix-conflict", "sha": "111111"},
            "base": {"ref": CONST_GIT_MAIN_BRANCH},
            "user": {"login": BOT_USER},
            "labels": ["owner/human"],
        }
    )

    class FakeClient:
        def get_pull_status(self, repo: str, pull: int) -> PullStatus:
            return bot_status

    class FakeSession:
        client = FakeClient()

    monkeypatch.setattr(fix_conflict, "get_github_session", lambda: FakeSession())

    report = run_fix_conflict(store, REPO, num)
    assert report.result == FixConflictResult.REFUSED
    assert "owner label" in report.reason or "claimed" in report.reason


def test_caps_hold(monkeypatch: pytest.MonkeyPatch) -> None:
    """Soft cap of 2 and hard cap of 4 rounds hold."""
    store = InMemoryRoadmapStore(repo=REPO)
    num = store.seed_issue(
        title="feat: something", labels=("status/in-progress", "priority/p2-medium")
    )
    item = store.item(num)
    assert item is not None
    store.set_marks(
        item,
        {
            FixConflictRecordKey.ROUNDS: "4",
            FixConflictRecordKey.FILES: json.dumps(["file1.py"]),
        },
    )

    bot_status = PullStatus.model_validate(
        {
            "state": "open",
            "draft": False,
            "head": {"ref": f"feat/{num}-fix-conflict", "sha": "111111"},
            "base": {"ref": CONST_GIT_MAIN_BRANCH},
            "user": {"login": BOT_USER},
            "labels": [],
        }
    )

    class FakeClient:
        def get_pull_status(self, repo: str, pull: int) -> PullStatus:
            return bot_status

    class FakeSession:
        client = FakeClient()

    monkeypatch.setattr(fix_conflict, "get_github_session", lambda: FakeSession())

    report = run_fix_conflict(store, REPO, num)
    assert report.result == FixConflictResult.STOPPED
    assert "Hard cap reached" in report.reason


def test_fix_conflict_report_to_json() -> None:
    rep = FixConflictReport(
        repo=REPO,
        pull=42,
        result=FixConflictResult.RESOLVED,
        head="sha123",
        rounds=2,
        files=("file1.py", "file2.py"),
        reason="settled",
    )
    data = json.loads(rep.to_json())
    assert data["repo"] == REPO
    assert data["pull"] == 42
    assert data["result"] == "resolved"
    assert data["head"] == "sha123"
    assert data["rounds"] == 2
    assert data["files"] == ["file1.py", "file2.py"]
    assert data["reason"] == "settled"


def test_admission_expected_head_mismatch_and_labels() -> None:
    status = PullStatus.model_validate(
        {
            "state": "open",
            "draft": False,
            "head": {"ref": BRANCH, "sha": "111111"},
            "base": {"ref": CONST_GIT_MAIN_BRANCH},
            "user": {"login": BOT_USER},
            "labels": ["owner/someone"],
        }
    )
    # Expected head mismatch
    err = fix_conflict.admission_bounds(status, None, expected_head="222222")
    assert err is not None
    assert "head moved" in err

    # PR holds owner label
    err2 = fix_conflict.admission_bounds(status, None)
    assert err2 is not None
    assert "PR holds owner label" in err2

    # Item claimed
    store = InMemoryRoadmapStore(repo=REPO)
    num = store.seed_issue(
        title="feat: test",
        labels=("status/in-progress", "priority/p2-medium", "owner/human"),
    )
    item = store.item(num)
    status_clean = PullStatus.model_validate(
        {
            "state": "open",
            "draft": False,
            "head": {"ref": BRANCH, "sha": "111111"},
            "base": {"ref": CONST_GIT_MAIN_BRANCH},
            "user": {"login": BOT_USER},
            "labels": [],
        }
    )
    err3 = fix_conflict.admission_bounds(status_clean, item)
    assert err3 is not None
    assert "owner" in err3


def test_the_service_claim_label_does_not_stop_the_admission() -> None:
    """The label of the Service's own claim is `owner/service`, in lower case like each label of
    the family, and it claims nothing against the step (#5027)."""
    store = InMemoryRoadmapStore(repo=REPO)
    number = store.seed_issue(
        title="feat: test", labels=("status/in-progress", "priority/p2-medium", "owner/service")
    )
    status = PullStatus.model_validate(
        {
            "state": "open",
            "draft": False,
            "head": {"ref": BRANCH, "sha": "111111"},
            "base": {"ref": CONST_GIT_MAIN_BRANCH},
            "user": {"login": BOT_USER},
            "labels": ["owner/service"],
        }
    )

    assert fix_conflict.admission_bounds(status, store.item(number)) is None


def test_conflict_caps_helper() -> None:
    from devops_cli.config.settings import load_settings

    settings = load_settings().roadmap.fix_conflict

    # Hard cap
    err = fix_conflict.check_conflict_caps(4, ["a.py"], ["a.py"], settings)
    assert err is not None
    assert "Hard cap reached" in err

    # Soft cap without reduction
    err2 = fix_conflict.check_conflict_caps(2, ["a.py", "b.py"], ["a.py"], settings)
    assert err2 is not None
    assert "Soft cap reached" in err2

    # Soft cap with reduction
    err3 = fix_conflict.check_conflict_caps(2, ["a.py"], ["a.py", "b.py"], settings)
    assert err3 is None


def test_merge_tree_conflict_helper(tmp_path: Path) -> None:
    repo = tmp_path / "tree_repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Bot")
    _git(repo, "config", "user.email", "bot@example.com")
    (repo / "file.txt").write_text("v1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "init")

    _git(repo, "checkout", "-b", "feat/branch")
    (repo / "file.txt").write_text("v1\nbranch\n", encoding="utf-8")
    _git(repo, "commit", "-am", "branch")

    _git(repo, "checkout", "main")
    (repo / "file.txt").write_text("v1\nmain\n", encoding="utf-8")
    _git(repo, "commit", "-am", "main")

    has_conflict, files = check_merge_tree_conflict(repo, "main", "feat/branch")
    assert has_conflict is True
    assert files == ["file.txt"]


def test_fix_conflict_cmd_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    import typer

    from devops_cli.commands.roadmap_step_fix_conflict import fix_conflict_cmd
    from devops_cli.exceptions import DevOpsCLIError

    # missing pull raises
    with pytest.raises(typer.Exit) as exc_info:
        fix_conflict_cmd(pull=None)
    assert exc_info.value.exit_code != 0

    # dry run returns early
    fix_conflict_cmd(repo="example/project", pull=42, dry_run=True)

    fake_report = FixConflictReport(
        repo="example/project",
        pull=42,
        result=FixConflictResult.RESOLVED,
        head="abcd123",
        rounds=1,
    )

    monkeypatch.setattr(fix_conflict, "run_fix_conflict", lambda *args, **kwargs: fake_report)

    # run successfully
    fix_conflict_cmd(repo="example/project", pull=42)

    # error handling
    def raise_err(*args: Any, **kwargs: Any) -> Any:
        raise DevOpsCLIError("fake failure")

    monkeypatch.setattr(fix_conflict, "run_fix_conflict", raise_err)
    with pytest.raises(typer.Exit) as exc_info2:
        fix_conflict_cmd(repo="example/project", pull=42)
    assert exc_info2.value.exit_code != 0


def _pull_status(sha: str, branch: str) -> PullStatus:
    return PullStatus.model_validate(
        {
            "state": "open",
            "draft": False,
            "head": {"ref": branch, "sha": sha},
            "base": {"ref": "main"},
            "user": {"login": BOT_USER},
            "labels": [],
        }
    )


def test_run_fix_conflict_scenarios(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A branch with no conflict, a branch with a commit of a person, and a conflict in a source
    file, which the plan names and a confirmed round stops on."""
    origin_dir = tmp_path / "origin.git"
    origin_dir.mkdir()
    subprocess.run([CONST_GIT_CLI, "init", "--bare", "-b", "main", str(origin_dir)], check=True)

    clone_dir = tmp_path / "local"
    subprocess.run([CONST_GIT_CLI, "clone", str(origin_dir), str(clone_dir)], check=True)
    _bot(clone_dir)

    (clone_dir / "base.txt").write_text("v1\n", encoding="utf-8")
    _git(clone_dir, "add", "-A")
    _git(clone_dir, "commit", "-m", "chore: base")
    _git(clone_dir, "push", "origin", "main")

    store = InMemoryRoadmapStore(repo=REPO)
    num = store.seed_issue(title="feat: item", labels=("status/in-progress", "priority/p2-medium"))

    # 1. No conflict
    branch_clean = f"feat/{num}-clean"
    _git(clone_dir, "checkout", "-b", branch_clean)
    (clone_dir / "new_file.txt").write_text("clean\n", encoding="utf-8")
    _git(clone_dir, "add", "-A")
    _git(clone_dir, "commit", "-m", "clean commit")
    _git(clone_dir, "push", "origin", branch_clean)
    _fake_github(
        monkeypatch, _pull_status(_git(clone_dir, "rev-parse", "HEAD"), branch_clean), origin_dir
    )
    rep = run_fix_conflict(store, REPO, num)
    assert rep.result == FixConflictResult.NO_CONFLICT

    # 2. A commit of a person: the clone of a confirmed round fails on it
    _git(clone_dir, "config", "user.name", "Alice Human")
    (clone_dir / "human.txt").write_text("human\n", encoding="utf-8")
    _git(clone_dir, "add", "-A")
    _git(clone_dir, "commit", "-m", "human commit")
    _git(clone_dir, "push", "origin", branch_clean)
    _fake_github(
        monkeypatch, _pull_status(_git(clone_dir, "rev-parse", "HEAD"), branch_clean), origin_dir
    )
    rep_human = run_fix_conflict(store, REPO, num, confirm=True)
    assert rep_human.result == FixConflictResult.FAILED
    assert "Alice Human, not by the App" in rep_human.reason

    # 3. A conflict in a source file: the plan without --confirm, and a stop of tier 1 with it
    _git(clone_dir, "checkout", "main")
    (clone_dir / "base.txt").write_text("main update\n", encoding="utf-8")
    _git(clone_dir, "commit", "-am", "main conflict update")
    _git(clone_dir, "push", "origin", "main")
    branch_code = f"feat/{num}-code-conflict"
    _git(clone_dir, "checkout", "-b", branch_code, "HEAD~1")
    _bot(clone_dir)
    (clone_dir / "base.txt").write_text("branch conflict update\n", encoding="utf-8")
    _git(clone_dir, "commit", "-am", "branch code update")
    _git(clone_dir, "push", "origin", branch_code)
    _fake_github(
        monkeypatch, _pull_status(_git(clone_dir, "rev-parse", "HEAD"), branch_code), origin_dir
    )
    rep_plan = run_fix_conflict(store, REPO, num, confirm=False)
    assert (rep_plan.result, rep_plan.files) == (FixConflictResult.PLANNED, ("base.txt",))
    assert rep_plan.reason.startswith("Plan: stop, because tier 1 settles only")
    rep_code = run_fix_conflict(store, REPO, num, confirm=True)
    assert rep_code.result == FixConflictResult.STOPPED
    assert "could not be resolved by Tier 1" in rep_code.reason


def test_fix_conflict_internal_helpers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # 2. is_release_path diff hunk: only the version line of pyproject.toml is release metadata
    assert is_release_path("pyproject.toml", '-  version = "1.2.3"')
    assert not is_release_path("some/file.py", '+__version__ = "1.2.3"')
    assert not is_release_path("some/file.py", '+version = "1.2.3"')
    assert not is_release_path("some/file.py", "+something_else = 1")

    # 3. record_fix_conflict_marks with None store or None item
    fix_conflict.record_fix_conflict_marks(
        None, None, rounds=1, files=[], result=FixConflictResult.RESOLVED
    )
    store = InMemoryRoadmapStore(repo=REPO)
    fix_conflict.record_fix_conflict_marks(
        store, None, rounds=1, files=[], result=FixConflictResult.RESOLVED
    )

    # 4. read_item_conflict_state with None or invalid json
    assert fix_conflict.read_item_conflict_state(None) == (0, [])
    num = store.seed_issue(title="feat: item", labels=("status/in-progress", "priority/p2-medium"))
    item = store.item(num)
    assert item is not None
    item.job_record[FixConflictRecordKey.FILES] = "not-json"
    assert fix_conflict.read_item_conflict_state(item) == (0, [])

    # 5. validate_strict_specs
    monkeypatch.setattr(
        fix_conflict,
        "run_subprocess",
        lambda *args, **kwargs: subprocess.CompletedProcess([], 0, stdout="ok", stderr=""),
    )
    assert fix_conflict.validate_strict_specs(tmp_path) is True
    monkeypatch.setattr(
        fix_conflict,
        "run_subprocess",
        lambda *args, **kwargs: subprocess.CompletedProcess([], 1, stdout="", stderr="err"),
    )
    assert fix_conflict.validate_strict_specs(tmp_path) is False

    # 6. admission_bounds with claimed_by and owner label
    num_owner = store.seed_issue(
        title="feat: item owner", labels=("owner/infra", "priority/p2-medium")
    )
    item_owner = store.item(num_owner)
    assert item_owner is not None

    status = PullStatus.model_validate(
        {
            "state": "open",
            "draft": False,
            "head": {"ref": "feat/42-x", "sha": "abc"},
            "base": {"ref": "main"},
            "user": {"login": "bot[bot]"},
            "labels": [],
        }
    )
    err = fix_conflict.admission_bounds(status, item_owner)
    assert err
    assert "holds owner label" in err

    num_claimed = store.seed_issue(title="feat: item claimed", labels=("priority/p2-medium",))
    item_claimed = store.item(num_claimed)
    assert item_claimed is not None
    # Simulate a human claim
    item_claimed = item_claimed.model_copy(update={"owner": "human"})

    err2 = fix_conflict.admission_bounds(status, item_claimed)
    assert err2
    assert "claimed by" in err2


def test_a_clone_that_fails_ends_the_round(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """`prepare` clones the repository into the work folder of the run (`clone_branch`). A clone
    that fails ends the round with `failed`."""

    def refused(work: Path, **kwargs: Any) -> Any:
        assert work.is_dir()
        raise GitOperationError("clone failed", operation="test")

    _fake_github(monkeypatch, _pull_status("1" * 40, BRANCH), tmp_path / "origin.git")
    monkeypatch.setattr(fix_conflict_phases, "clone_branch", refused)

    report = run_fix_conflict(InMemoryRoadmapStore(repo=REPO), REPO, 42)

    assert (report.result, report.reason) == (FixConflictResult.FAILED, "clone failed")


# Tier 1 runs code of the checkout of the pull request: `uv run devops docs generate` and `uv lock`
# start the entry point of the project and its build hooks. The double of the `uv` process writes
# one of these into the clone, as such code can.
_WRITTEN = (
    "pre-push hook",
    "remote.origin.pushurl",
    "remote.origin.receivepack",
    "url.insteadOf",
    "reference-transaction hook",
)
_SPEC = "openspec/specs/test-cap/spec.md"
_DOCS = "docs/CLI_REFERENCE.md"
_LOCK = "uv.lock"
_NOT_SETTLED = "Conflict could not be resolved by Tier 1"


@dataclass(frozen=True)
class _Pull:
    """A bot pull request on the bare repository `upstream` that conflicts with main; the clone of
    the step; another bare repository with the same head branch, whose pre-receive hook writes the
    token that it gets into `seen` and refuses the push; and `seen`, where each program of the
    clone writes."""

    upstream: Path
    other: Path
    clone: Path
    seen: Path
    branch: str
    head: str
    number: int
    store: InMemoryRoadmapStore

    def status(self) -> PullStatus:
        return PullStatus.model_validate(
            {
                "state": "open",
                "draft": False,
                "head": {"ref": self.branch, "sha": self.head},
                "base": {"ref": CONST_GIT_MAIN_BRANCH},
                "user": {"login": BOT_USER},
                "labels": [],
            }
        )

    def pushed(self) -> str:
        """The tip of the head branch on `upstream`."""
        return _git(self.upstream, "rev-parse", f"refs/heads/{self.branch}")

    def pushed_file(self, name: str) -> str:
        """The text of `name` at the tip of the head branch on `upstream`, or "" with no file."""
        found = subprocess.run(
            [CONST_GIT_CLI, "-C", str(self.upstream), "show", f"{self.branch}:{name}"],
            capture_output=True,
            text=True,
        )
        return found.stdout if found.returncode == 0 else ""

    def written(self) -> list[str]:
        """What the programs of the clone wrote into `seen`."""
        return sorted(path.name for path in self.seen.iterdir())


def _record(target: Path) -> str:
    """A shell line that writes the GitHub token of its environment into `target`."""
    return f"printf '%s' \"$GH_TOKEN\" > '{target}'"


def _bot(clone: Path) -> None:
    _git(clone, "config", "user.name", BOT_USER)
    _git(clone, "config", "user.email", BOT_EMAIL)


def _commit_files(seed: Path, files: dict[str, str | None], message: str) -> None:
    """Commit `files` in `seed`: a text writes the file, None removes it."""
    for name, text in files.items():
        if text is None:
            (seed / name).unlink()
            continue
        (seed / name).parent.mkdir(parents=True, exist_ok=True)
        (seed / name).write_text(text, encoding="utf-8")
    _git(seed, "add", "-A")
    _git(seed, "commit", "-q", "-m", message)


def _repositories(tmp_path: Path) -> tuple[Path, Path, Path, Path, InMemoryRoadmapStore, int]:
    """The bare `upstream` and other repositories, `seen`, the seed clone with the identity of a
    person, and the store with the item."""
    upstream, other, seen, seed = (tmp_path / name for name in ("up.git", "other.git", "seen", "s"))
    seen.mkdir()
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(upstream))
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(other))
    _git(tmp_path, "clone", "-q", str(upstream), str(seed))
    _git(seed, "config", "user.name", "Alice Human")
    _git(seed, "config", "user.email", "alice@example.com")
    _commit_files(seed, {STEPS_FILE: STEPS_DECLARATION}, "chore: declare the steps")
    store = InMemoryRoadmapStore(repo=REPO)
    number = store.seed_issue(
        title="feat: test", labels=("status/in-progress", "priority/p2-medium")
    )
    return upstream, other, seen, seed, store, number


def _finish(
    tmp_path: Path, parts: tuple[Path, Path, Path, Path, InMemoryRoadmapStore, int], branch: str
) -> _Pull:
    """Push the head branch to `upstream` and to the other repository, arm the hook of the other
    repository, and clone `upstream` as the clone of the step, with the identity of the bot."""
    upstream, other, seen, seed, store, number = parts
    _git(seed, "push", "-q", "origin", "main", branch)
    _git(seed, "push", "-q", str(other), branch)
    receive = other / "hooks" / "pre-receive"
    receive.write_text(f"#!/bin/sh\n{_record(seen / 'other')}\nexit 1\n", encoding="utf-8")
    receive.chmod(0o755)
    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "-q", str(upstream), str(clone))
    _bot(clone)
    head = _git(seed, "rev-parse", branch)
    return _Pull(upstream, other, clone, seen, branch, head, number, store)


def _spec(text: str = "") -> dict[str, str | None]:
    return {_SPEC: f"# Test Spec\n\n## Requirements\nInitial req.\n{text}"}


def _pull_with_archive_conflict(
    tmp_path: Path,
    *,
    after: bool = False,
    squashed: bool = False,
    spec_fix: bool = False,
    docs: bool = False,
    archived: bool = True,
    other_item: bool = False,
) -> _Pull:
    """A bot pull request whose archive commit conflicts with main on `_SPEC`. With `after`, a bot
    commit follows the archive commit. With `squashed`, one commit holds the code, the change and
    its archive. With `spec_fix`, a bot commit after the archive changes only the spec. With
    `docs`, the archive commit and main also change a generated document. With no `archived`, a
    commit that changes only the spec takes the place of the archive commit. With `other_item`, the
    archive commit also archives the change of another item."""
    parts = _repositories(tmp_path)
    seed, number = parts[3], parts[5]
    _commit_files(seed, {**_spec(), _DOCS: "# v1\n"}, "chore: initial specs")
    _bot(seed)
    branch = f"feat/{number}-test-cap"
    _git(seed, "checkout", "-q", "-b", branch)
    change = f"openspec/changes/{number}-test-cap/tasks.md"
    other = {"openspec/changes/41-other/tasks.md": "- [x] other\n"} if other_item else {}
    feat = {change: "- [x] task done\n", "src/a.py": "A = 1\n", **other}
    _commit_files(seed, feat, f"feat: {number}")
    moved = f"openspec/changes/archive/2026-11-16-{number}-test-cap/tasks.md"
    files = {**_spec(f"Added req {number}.\n"), change: None, moved: "- [x] task done\n"}
    if other_item:
        files["openspec/changes/41-other/tasks.md"] = None
        files["openspec/changes/archive/2026-11-16-41-other/tasks.md"] = "- [x] other\n"
    if not archived:
        files = _spec(f"Added req {number}.\n")
    _commit_files(seed, {**files, **({_DOCS: "# v1\narchive\n"} if docs else {})}, "docs: specs")
    if squashed:
        _git(seed, "reset", "-q", "--soft", "HEAD~2")
        _git(seed, "commit", "-q", "-m", f"feat: implement {number}")
    if after:
        _commit_files(seed, {"src/fix.py": "F = 1\n"}, "fix: a check")
    if spec_fix:
        _commit_files(seed, _spec(f"Added req {number}, fixed by the bot.\n"), "fix: spec wording")
    _git(seed, "checkout", "-q", "main")
    _git(seed, "config", "user.name", "Alice Human")
    main = {**_spec("Main req concurrent.\n"), **({_DOCS: "# v1\nmain\n"} if docs else {})}
    _commit_files(seed, main, "chore: concurrent spec update")
    return _finish(tmp_path, parts, branch)


_DOCS_BASE: dict[str, str | None] = {_DOCS: "# v1\n", _LOCK: "version = 1\n"}
_DOCS_BRANCH: dict[str, str | None] = {
    _DOCS: "# v1\nbranch\n",
    _LOCK: "version = 1\nbranch\n",
    "src/feature.py": "A = 1\n",
}
_DOCS_MAIN: dict[str, str | None] = {_DOCS: "# v1\nmain\n", _LOCK: "version = 1\nmain\n"}


def _pull_with_docs_conflict(
    tmp_path: Path,
    *,
    base: dict[str, str | None] = _DOCS_BASE,
    branch_files: dict[str, str | None] = _DOCS_BRANCH,
    main: dict[str, str | None] = _DOCS_MAIN,
    clean_first: bool = False,
    merge_main: bool = False,
) -> _Pull:
    """A bot pull request whose generated document and `uv.lock` conflict with main. A person wrote
    the base commit and the commits of main. With `clean_first` the branch starts with a commit
    that applies with no conflict. With `merge_main` the bot merges main into the branch."""
    parts = _repositories(tmp_path)
    seed, number = parts[3], parts[5]
    _commit_files(seed, base, "chore: base")
    branch = f"feat/{number}-docs"
    _git(seed, "checkout", "-q", "-b", branch)
    _bot(seed)
    if clean_first:
        _commit_files(seed, {"src/clean.py": "B = 2\n"}, "feat: a clean change")
    _commit_files(seed, branch_files, "feat: a feature")
    if merge_main:
        _git(seed, "checkout", "-q", "main")
        _git(seed, "config", "user.name", "Alice Human")
        _commit_files(seed, {"src/main.py": "M = 1\n"}, "chore: a change of main")
        _git(seed, "checkout", "-q", branch)
        _bot(seed)
        _git(seed, "merge", "-q", "--no-edit", "main")
        _commit_files(seed, {"src/after.py": "C = 3\n"}, "feat: after the merge")
    _git(seed, "checkout", "-q", "main")
    _git(seed, "config", "user.name", "Alice Human")
    _commit_files(seed, main, "chore: main")
    return _finish(tmp_path, parts, branch)


def _write_into_clone(pull: _Pull, checkout: Path, written: str | None) -> None:
    """What the code of the pull request writes into the clone."""
    if written == "pre-push hook":
        hook = checkout / ".git" / "hooks" / "pre-push"
        hook.write_text(f"#!/bin/sh\n{_record(pull.seen / 'hook')}\n", encoding="utf-8")
        hook.chmod(0o755)
    elif written == "remote.origin.pushurl":
        _git(checkout, "config", written, str(pull.other))
    elif written == "remote.origin.receivepack":
        _git(checkout, "config", written, f"{_record(pull.seen / 'receivepack')}; git-receive-pack")
    elif written == "url.insteadOf":
        _git(checkout, "config", f"url.{pull.other}.insteadOf", str(pull.upstream))
    elif written == "reference-transaction hook":
        # A hook that refuses an update of a remote-tracking ref in the clone, as the update after
        # a push from the clone (#6640). The rebase moves no remote-tracking ref.
        hook = checkout / ".git" / "hooks" / "reference-transaction"
        refused = f"refs/remotes/*) {_record(pull.seen / 'refhook')}; exit 1;;"
        body = f'[ "$1" = prepared ] || exit 0\nwhile read -r _ _ ref; do case "$ref" in {refused} esac; done\n'
        hook.write_text(f"#!/bin/sh\n{body}", encoding="utf-8")
        hook.chmod(0o755)


def _with_pull_request_code(
    monkeypatch: pytest.MonkeyPatch,
    pull: _Pull,
    written: str | None = None,
    *,
    valid: bool = True,
    fails: str | None = None,
    timeout: str | None = None,
) -> list[list[str]]:
    """Run the step against `pull`: GitHub gives its status, each `uv` process is the code of the
    pull request, `openspec archive` moves the change folder and `openspec validate` gives
    `valid`. git runs for real through the process runner, which gives the token to each git
    child. The list holds each `uv` process."""
    ran: list[list[str]] = []

    def archive(cwd: Path) -> None:
        changes = cwd / "openspec" / "changes"
        active = changes / f"{pull.number}-test-cap"
        shutil.move(active, changes / "archive" / f"2026-11-21-{pull.number}-test-cap")

    def run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if cmd[0] == BIN_UV:
            ran.append(cmd)
            if fails is not None and fails in cmd:
                return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="it failed: MARK-7f3a")
            if timeout is not None and timeout in cmd:
                raise subprocess.TimeoutExpired(cmd, 1800)
            if "openspec" in cmd and "archive" in cmd:
                archive(Path(kwargs["cwd"]))
            _write_into_clone(pull, Path(kwargs["cwd"]), written)
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if cmd[0] == BIN_OPENSPEC:
            return subprocess.CompletedProcess(cmd, 0 if valid else 1, stdout="", stderr="")
        return run_subprocess(cmd, **kwargs)

    _fake_github(monkeypatch, pull.status(), pull.upstream)
    monkeypatch.setattr(fix_conflict, "run_subprocess", run)
    return ran


def test_without_confirm_the_step_runs_no_code_of_the_pull_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without --confirm, as on a workstation, the step finds the conflict and returns its plan,
    which names the runner Job. It runs no fixer of tier 1, pushes nothing and writes no record."""
    pull = _pull_with_archive_conflict(tmp_path)
    ran = _with_pull_request_code(monkeypatch, pull, "pre-push hook")

    report = run_fix_conflict(pull.store, REPO, pull.number)

    assert ran == []
    assert pull.written() == []
    assert (report.result, report.files) == (FixConflictResult.PLANNED, (_SPEC,))
    assert report.reason.startswith("Plan: drop the archive commit of the item")
    assert "runner Job" in report.reason
    assert pull.pushed() == pull.head
    item = pull.store.item(pull.number)
    assert item is not None
    assert FixConflictRecordKey.RESULT not in item.job_record


@pytest.mark.parametrize("written", _WRITTEN)
def test_a_confirmed_round_pushes_only_to_the_url_that_it_read_after_the_clone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, config: Callable[..., Path], written: str
) -> None:
    """With --confirm, in a runner Job, tier 1 runs code of the pull request, and that code can
    write a hook or a git setting into the clone. `publish` pushes from a new repository, which no
    code of the pull request touched, to the repository on GitHub."""
    config(roadmap={"implement": {"in_runner": True}})
    pull = _pull_with_archive_conflict(tmp_path)
    ran = _with_pull_request_code(monkeypatch, pull, written)

    report = run_fix_conflict(pull.store, REPO, pull.number, confirm=True)

    assert ran
    assert pull.written() == []
    assert report.result == FixConflictResult.RESOLVED
    assert pull.pushed() == report.head != pull.head


def test_the_three_phases_on_one_run_folder_settle_and_push(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`prepare`, `agent` and `publish` run one after the other on one run folder, as the three
    containers of #3700 run them (#6703). The agent phase makes no GitHub call, tier 1 runs only
    in it, and `publish` pushes the settled branch with a lease on the judged head."""
    pull = _pull_with_archive_conflict(tmp_path)
    ran = _with_pull_request_code(monkeypatch, pull)
    folders = RunFolders(tmp_path / "run")
    client = fix_conflict.get_github_session().client

    prepared = fix_conflict_phases.prepare_phase(
        pull.store, client, REPO, pull.number, head=pull.head, folders=folders
    )
    assert (prepared, ran) == (None, [])

    def no_github() -> Any:
        raise AssertionError("the agent phase makes no GitHub call")

    for module in (fix_conflict, fix_conflict_phases, phases_checkout):
        monkeypatch.setattr(module, "get_github_session", no_github)
    fix_conflict_phases.agent_phase(folders)
    assert ran
    _with_pull_request_code(monkeypatch, pull)

    # The container `publish` mounts the run folder read-only (#3700).
    with read_only_run(folders):
        report = fix_conflict_phases.publish_phase(
            pull.store, client, folders, repo=REPO, pull=pull.number
        )

    assert report is not None
    assert (report.result, report.rounds) == (FixConflictResult.RESOLVED, 1)
    assert pull.pushed() == report.head != pull.head


def test_an_archive_commit_that_is_not_the_tip_is_dropped_and_written_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """At the stop on the archive commit, the round runs `git rebase --skip`, so HEAD stays on the
    head branch and the commit after the archive commit stays. After the rebase it archives the
    change again, in a commit of its own on the tip."""
    pull = _pull_with_archive_conflict(tmp_path, after=True)
    _with_pull_request_code(monkeypatch, pull)

    report = run_fix_conflict(pull.store, REPO, pull.number, confirm=True)

    assert (report.result, report.reason) == (FixConflictResult.RESOLVED, "")
    assert pull.pushed_file("src/fix.py") == "F = 1\n"
    assert pull.pushed_file("src/a.py") == "A = 1\n"
    assert pull.pushed_file(f"openspec/changes/archive/2026-11-21-{pull.number}-test-cap/tasks.md")
    subject = _git(pull.upstream, "log", "-1", "--format=%s", pull.branch)
    assert subject == f"docs(spec): archive the change (#{pull.number})"


def test_an_archive_commit_that_holds_other_paths_stops_the_round(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The round drops a commit only when each of its paths is an OpenSpec path or a generated
    document. A commit that also holds code, such as one squashed commit, stops the round, and the
    head branch does not change."""
    pull = _pull_with_archive_conflict(tmp_path, squashed=True)
    ran = _with_pull_request_code(monkeypatch, pull)

    report = run_fix_conflict(pull.store, REPO, pull.number, confirm=True)

    assert (report.result, report.reason) == (
        FixConflictResult.STOPPED,
        "Conflict could not be resolved by Tier 1",
    )
    assert (ran, pull.pushed()) == ([], pull.head)


@pytest.mark.parametrize(
    "variant",
    [{"spec_fix": True}, {"archived": False}, {"other_item": True}],
    ids=["a spec fix after the archive", "a spec commit with no archive", "two items archived"],
)
def test_a_conflicting_spec_commit_that_is_no_archive_commit_stops_the_round(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, variant: dict[str, bool]
) -> None:
    """The round drops only the archive commit of the item, which moves its change folder into the
    archive and touches no other change. Another commit with only OpenSpec paths, such as a fix of
    the spec after the archive, a spec commit of a pull request that never archived, or a commit
    that also archives another item, stops the round when it conflicts."""
    pull = _pull_with_archive_conflict(tmp_path, **variant)
    _with_pull_request_code(monkeypatch, pull)

    report = run_fix_conflict(pull.store, REPO, pull.number, confirm=True)

    assert (report.result, report.reason) == (FixConflictResult.STOPPED, _NOT_SETTLED)
    assert pull.pushed() == pull.head


def test_an_archive_commit_whose_generated_document_conflicts_too_is_dropped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The archive commit that a round writes also holds the generated documents. When main changes
    the spec and such a document, tier 1 takes main for the document first, then drops the archive
    commit and archives the change again."""
    pull = _pull_with_archive_conflict(tmp_path, docs=True)
    _with_pull_request_code(monkeypatch, pull)

    plan = run_fix_conflict(pull.store, REPO, pull.number)
    report = run_fix_conflict(pull.store, REPO, pull.number, confirm=True)

    assert plan.reason.startswith("Plan: drop the archive commit of the item")
    assert (report.result, report.reason) == (FixConflictResult.RESOLVED, "")
    subject = _git(pull.upstream, "log", "-1", "--format=%s", pull.branch)
    assert subject == f"docs(spec): archive the change (#{pull.number})"


def test_a_generated_document_that_main_deleted_stays_deleted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Main deleted a generated document that the pull request changed. At that stop ("deleted by
    us") tier 1 takes main's side as a developer does, `git rm`, and continues."""
    old = "docs/commands/old.md"
    pull = _pull_with_docs_conflict(
        tmp_path,
        base={old: "# old\n"},
        branch_files={old: "# old\nbranch\n", "src/feature.py": "A = 1\n"},
        main={old: None},
    )
    _with_pull_request_code(monkeypatch, pull)

    report = run_fix_conflict(pull.store, REPO, pull.number, confirm=True)

    assert (report.result, report.reason) == (FixConflictResult.RESOLVED, "")
    assert (pull.pushed_file(old), pull.pushed_file("src/feature.py")) == ("", "A = 1\n")


def test_a_round_that_git_refuses_stops_and_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A git call of tier 1 that fails ends the round as a stop: the rebase is aborted, the stop is
    recorded, and the head branch does not change."""
    pull = _pull_with_docs_conflict(tmp_path)
    _with_pull_request_code(monkeypatch, pull)

    def refused(*args: Any, **kwargs: Any) -> Any:
        raise GitOperationError("git checkout failed", operation="test")

    monkeypatch.setattr(fix_conflict_phases, "rebase_onto", refused)

    report = run_fix_conflict(pull.store, REPO, pull.number, confirm=True)

    assert (report.result, report.reason) == (FixConflictResult.STOPPED, "git checkout failed")
    assert pull.pushed() == pull.head
    item = pull.store.item(pull.number)
    assert item is not None
    assert item.job_record.get(FixConflictRecordKey.ROUNDS) == "1"


def test_a_skip_that_git_refuses_stops_the_round(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each `--skip` or `--continue` moves the rebase on or stops the round. A call that fails and
    leaves the rebase on the same commit is a stop of git, which the round records."""
    from devops_cli.roadmap import clone_git

    pull = _pull_with_archive_conflict(tmp_path)
    _with_pull_request_code(monkeypatch, pull)
    code = clone_git.run_subprocess
    skips: list[int] = []

    def refused(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if cmd[-2:] == ["rebase", "--skip"]:
            skips.append(1)
            if len(skips) > 3:
                raise RuntimeError("the round skips again and again")
            return subprocess.CompletedProcess(cmd, 128, "", "fatal: could not discard changes")
        return code(cmd, **kwargs)

    monkeypatch.setattr(clone_git, "run_subprocess", refused)

    report = run_fix_conflict(pull.store, REPO, pull.number, confirm=True)

    assert (report.result, report.reason) == (
        FixConflictResult.STOPPED,
        "`git rebase --skip` failed: fatal: could not discard changes",
    )
    assert (len(skips), pull.pushed()) == (1, pull.head)


@pytest.mark.parametrize("ending", ["validation fails", "the remote refuses", "nothing past main"])
def test_each_round_that_ends_unsettled_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ending: str
) -> None:
    """A round that runs and does not settle the pull request, for any cause, adds one to the
    rounds of the record, so the caps hold."""
    only = {_DOCS: "# v1\nbranch only\n", _LOCK: "version = 1\nbranch only\n"}
    pull = _pull_with_docs_conflict(
        tmp_path, **({"branch_files": only} if ending == "nothing past main" else {})
    )
    _with_pull_request_code(monkeypatch, pull, valid=ending != "validation fails")
    if ending == "the remote refuses":
        hook = pull.upstream / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        hook.chmod(0o755)

    report = run_fix_conflict(pull.store, REPO, pull.number, confirm=True)

    item = pull.store.item(pull.number)
    assert item is not None
    assert report.result in (FixConflictResult.FAILED, FixConflictResult.STOPPED)
    assert (item.job_record.get(FixConflictRecordKey.ROUNDS), report.rounds) == ("1", 1)
    assert pull.pushed() == pull.head


def test_a_generated_document_that_both_sides_renamed_takes_main(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Main renames a generated page to one name and the pull request to another. The stop holds
    the page with no version of main (`UA`); tier 1 removes it, as it removes a page that main
    deleted, and keeps the page of main."""
    page = "# page\n" + "".join(f"line {n}\n" for n in range(20))
    pull = _pull_with_docs_conflict(
        tmp_path,
        base={"docs/commands/x.md": page},
        branch_files={"docs/commands/x.md": None, "docs/commands/z.md": page, "src/a.py": "1\n"},
        main={"docs/commands/x.md": None, "docs/commands/y.md": page},
    )
    _with_pull_request_code(monkeypatch, pull)

    report = run_fix_conflict(pull.store, REPO, pull.number, confirm=True)

    assert (report.result, report.reason) == (FixConflictResult.RESOLVED, "")
    pages = [pull.pushed_file(f"docs/commands/{name}.md") for name in "xyz"]
    assert (pages, pull.pushed_file("src/a.py")) == (["", page, ""], "1\n")


def test_a_docs_and_lockfile_round_completes_with_no_environment_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A round on a conflict of a generated document and `uv.lock` continues the rebase with
    `-c core.editor=true`, generates both files again and pushes. No git call of the step sets an
    environment variable, because the process runner refuses an override such as `GIT_EDITOR`."""
    pull = _pull_with_docs_conflict(tmp_path)
    ran = _with_pull_request_code(monkeypatch, pull)
    code = fix_conflict.run_subprocess
    git_env: list[object] = []

    def spy(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if cmd[0] == CONST_GIT_CLI:
            git_env.append(kwargs.get("env"))
        return code(cmd, **kwargs)

    monkeypatch.setattr(fix_conflict, "run_subprocess", spy)

    report = run_fix_conflict(pull.store, REPO, pull.number, confirm=True)

    assert (report.result, report.reason) == (FixConflictResult.RESOLVED, "")
    assert [cmd[1:] for cmd in ran] == [["lock"], ["run", "devops", "docs", "generate"]]
    assert pull.pushed() == report.head != pull.head
    assert git_env
    assert set(git_env) == {None}


def test_a_round_that_leaves_no_commit_past_main_pushes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The pull request changes only the generated document and `uv.lock`, so tier 1 takes main
    for each and no commit stays past main. The round never pushes the tip of main over the pull
    request."""
    only = {_DOCS: "# v1\nbranch only\n", _LOCK: "version = 1\nbranch only\n"}
    pull = _pull_with_docs_conflict(tmp_path, branch_files=only)
    _with_pull_request_code(monkeypatch, pull)

    report = run_fix_conflict(pull.store, REPO, pull.number, confirm=True)

    assert (report.result, report.reason) == (
        FixConflictResult.FAILED,
        "The rebase left no commit past the tip of the default branch",
    )
    assert pull.pushed() == pull.head


def test_a_renamed_file_that_main_edited_is_pushed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The pull request renames a file that main edits. The rebase carries the edit of main into
    the renamed file, and the round pushes the result."""
    old = "".join(f"LINE_{n} = {n}\n" for n in range(40))
    pull = _pull_with_docs_conflict(
        tmp_path,
        base={**_DOCS_BASE, "src/old.py": old},
        branch_files={**_DOCS_BRANCH, "src/old.py": None, "src/new.py": old},
        main={**_DOCS_MAIN, "src/old.py": old.replace("LINE_39 = 39", "LINE_39 = 390")},
    )
    _with_pull_request_code(monkeypatch, pull)

    report = run_fix_conflict(pull.store, REPO, pull.number, confirm=True)

    assert (report.result, report.reason) == (FixConflictResult.RESOLVED, "")
    assert pull.pushed_file("src/new.py").endswith("LINE_39 = 390\n")
    assert pull.pushed_file("src/old.py") == ""


def test_a_merge_of_main_into_the_branch_is_no_commit_of_a_person(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The bot merged main into the branch. The authors of the pull request come from
    `person_authors`, which leaves the clean merge out, so the commits of main that the merge brings
    are no commits of a person. The plan names the conflict, and a confirmed round settles it."""
    pull = _pull_with_docs_conflict(tmp_path, merge_main=True)
    _with_pull_request_code(monkeypatch, pull)

    plan = run_fix_conflict(pull.store, REPO, pull.number)
    done = run_fix_conflict(pull.store, REPO, pull.number, confirm=True)

    assert (plan.result, plan.files) == (FixConflictResult.PLANNED, (_DOCS, _LOCK))
    assert (done.result, done.reason) == (FixConflictResult.RESOLVED, "")
    assert pull.pushed_file("src/after.py") == "C = 3\n"


def test_the_plan_and_the_round_settle_a_version_line_of_uv_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The `version =` line of a package in a conflict of `uv.lock` is no release metadata (#6623).
    The plan and the round use one rule: tier 1 takes the `uv.lock` of main, runs `uv lock`, and
    the round pushes the branch with no other change."""
    package = '[[package]]\nname = "foo"\nversion = "{}"\n'
    pull = _pull_with_docs_conflict(
        tmp_path,
        base={_LOCK: package.format("1.0.0")},
        branch_files={_LOCK: package.format("1.1.0"), "src/feature.py": "A = 1\n"},
        main={_LOCK: package.format("1.2.0")},
    )
    ran = _with_pull_request_code(monkeypatch, pull)

    plan = run_fix_conflict(pull.store, REPO, pull.number)
    done = run_fix_conflict(pull.store, REPO, pull.number, confirm=True)

    assert plan.reason.startswith("Plan: take the default branch for these files")
    assert (done.result, done.reason) == (FixConflictResult.RESOLVED, "")
    assert [cmd[1:] for cmd in ran] == [["lock"]]
    assert (pull.pushed_file(_LOCK), pull.pushed_file("src/feature.py")) == (
        package.format("1.2.0"),
        "A = 1\n",
    )
    assert _git(pull.upstream, "diff", "--name-only", "main", pull.branch) == "src/feature.py"


def test_the_plan_and_the_round_stop_on_the_version_line_of_pyproject(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A conflict on the version line of `pyproject.toml` is release metadata: the plan and the
    round stop, and tier 1 runs no fixer (#5019, #6623)."""
    project = '[project]\nname = "app"\nversion = "{}"\n'
    pull = _pull_with_docs_conflict(
        tmp_path,
        base={"pyproject.toml": project.format("1.0.0")},
        branch_files={"pyproject.toml": project.format("1.1.0"), "src/feature.py": "A = 1\n"},
        main={"pyproject.toml": project.format("1.2.0")},
    )
    ran = _with_pull_request_code(monkeypatch, pull)

    plan = run_fix_conflict(pull.store, REPO, pull.number)
    done = run_fix_conflict(pull.store, REPO, pull.number, confirm=True)

    assert plan.reason.startswith("Plan: stop on the release path")
    assert (done.result, done.reason) == (FixConflictResult.STOPPED, "Conflict on a release path")
    assert (ran, pull.pushed()) == ([], pull.head)


@pytest.mark.parametrize(
    ("conflicts", "mode", "release", "plan"),
    [
        ((_SPEC,), "on", False, "Plan: drop the archive commit of the item"),
        ((_DOCS, _SPEC), "on", False, "Plan: drop the archive commit of the item"),
        ((_DOCS, _LOCK), "on", False, "Plan: take the default branch for these files"),
        ((_LOCK,), "on", True, "Plan: stop on the release path"),
        (("src/feature.py",), "on", False, "Plan: stop, because tier 1 settles only"),
        ((_DOCS,), "plan", False, "Plan: stop, because roadmap.fix_conflict.tier1_mode is not on"),
    ],
)
def test_the_plan_says_what_a_confirmed_round_does(
    conflicts: tuple[str, ...], mode: str, release: bool, plan: str
) -> None:
    """The plan sorts the conflicted paths by the rules of tier 1, so it says that a confirmed
    round stops where it would stop."""
    assert fix_conflict.plan_reason(conflicts, mode, release).startswith(plan)


# ── The phases: the stops and the refusals (#6703) ──


@pytest.mark.parametrize(
    ("fails", "reason"),
    [("lock", "uv lock failed"), ("generate", "devops docs generate failed")],
)
def test_a_program_of_tier_1_that_fails_stops_the_round(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fails: str, reason: str
) -> None:
    """A program of tier 1 that fails at a stop ends the round as a stop that names it. The rebase
    is aborted, the round is recorded, and nothing is pushed."""
    pull = _pull_with_docs_conflict(tmp_path)
    _with_pull_request_code(monkeypatch, pull, fails=fails)

    report = run_fix_conflict(pull.store, REPO, pull.number, confirm=True)

    item = pull.store.item(pull.number)
    assert item is not None
    assert (report.result, report.rounds) == (FixConflictResult.STOPPED, 1)
    assert report.reason.startswith(reason)
    assert "MARK-7f3a" in report.reason
    assert (item.job_record.get(FixConflictRecordKey.ROUNDS), pull.pushed()) == ("1", pull.head)


def test_an_archive_that_fails_after_the_skip_stops_the_round(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The rebase skips the archive commit, and the archive again fails: the round stops with the
    output of the archive, and pushes nothing."""
    pull = _pull_with_archive_conflict(tmp_path)
    _with_pull_request_code(monkeypatch, pull, fails="archive")

    report = run_fix_conflict(pull.store, REPO, pull.number, confirm=True)

    assert report.result == FixConflictResult.STOPPED
    assert report.reason.startswith("The change could not be archived again: ")
    assert report.reason.endswith("exited with status 1. it failed: MARK-7f3a")
    assert pull.pushed() == pull.head


def test_with_tier_1_off_a_conflict_stops_the_round(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, config: Callable[..., Path]
) -> None:
    """With `roadmap.fix_conflict.tier1_mode` off, the rebase settles no stop: the round stops and
    runs no program of tier 1."""
    config(roadmap={"fix_conflict": {"tier1_mode": "off"}})
    pull = _pull_with_docs_conflict(tmp_path)
    ran = _with_pull_request_code(monkeypatch, pull)

    report = run_fix_conflict(pull.store, REPO, pull.number, confirm=True)

    assert (report.result, report.reason, ran) == (FixConflictResult.STOPPED, _NOT_SETTLED, [])
    assert pull.pushed() == pull.head


def test_a_soft_cap_with_no_fewer_files_stops_in_prepare(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The record holds two rounds on the same files, so `prepare` stops on the soft cap before the
    agent phase, and the round is not counted again."""
    pull = _pull_with_docs_conflict(tmp_path)
    ran = _with_pull_request_code(monkeypatch, pull)
    item = pull.store.item(pull.number)
    assert item is not None
    pull.store.set_marks(
        item,
        {FixConflictRecordKey.ROUNDS: "2", FixConflictRecordKey.FILES: json.dumps([_DOCS, _LOCK])},
    )

    report = run_fix_conflict(pull.store, REPO, pull.number, confirm=True)

    assert report.result == FixConflictResult.STOPPED
    assert report.reason.startswith("Soft cap reached")
    assert (ran, pull.pushed(), report.rounds) == ([], pull.head, 2)


def test_a_head_that_moved_before_the_clone_fails_the_round(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GitHub gives a head that the clone of the head branch does not hold, so `prepare` fails the
    round and runs no program of tier 1."""
    pull = _pull_with_docs_conflict(tmp_path)
    ran = _with_pull_request_code(monkeypatch, pull)
    _fake_github(monkeypatch, _pull_status("2" * 40, pull.branch), pull.upstream)

    report = run_fix_conflict(pull.store, REPO, pull.number, confirm=True)

    assert report.result == FixConflictResult.FAILED
    assert report.reason.startswith("The head branch is at")
    assert ran == []


def test_a_claim_during_the_round_refuses_the_push(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A person claims the item while the agent phase runs. `publish` checks the admission bounds
    again right before the push, so it pushes nothing."""
    pull = _pull_with_docs_conflict(tmp_path)
    _with_pull_request_code(monkeypatch, pull)
    agent = fix_conflict_phases.agent_phase

    def agent_then_claim(folders: RunFolders) -> None:
        agent(folders)
        pull.store.add_label(pull.number, "owner/agent")

    monkeypatch.setattr(fix_conflict_phases, "agent_phase", agent_then_claim)

    report = run_fix_conflict(pull.store, REPO, pull.number, confirm=True)

    item = pull.store.item(pull.number)
    assert item is not None
    assert report.result == FixConflictResult.REFUSED
    assert "owner label" in report.reason
    assert (pull.pushed(), item.job_record.get(FixConflictRecordKey.ROUNDS)) == (pull.head, "1")


def test_a_separate_publish_takes_only_the_state_of_its_round(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A separate `publish` reads the state file as data: a round that `prepare` ended gives no
    second report, and a state of another pull request or another head raises
    `PhaseOutputError`. A forged result of the agent raises it too."""
    from devops_cli.exceptions.roadmap import PhaseOutputError
    from devops_cli.roadmap.phases.files import AgentOutcome, OutcomeKind, write_json

    pull = _pull_with_docs_conflict(tmp_path)
    _with_pull_request_code(monkeypatch, pull)
    client = fix_conflict.get_github_session().client
    folders = RunFolders(tmp_path / "run")
    assert (
        fix_conflict_phases.prepare_phase(
            pull.store, client, REPO, pull.number, head=None, folders=folders
        )
        is None
    )

    with pytest.raises(PhaseOutputError, match="another pull request"):
        fix_conflict_phases.publish_phase(pull.store, client, folders, repo=REPO, pull=99)
    with pytest.raises(PhaseOutputError, match="another head"):
        fix_conflict_phases.publish_phase(
            pull.store, client, folders, repo=REPO, pull=pull.number, head="3" * 40
        )
    forged = AgentOutcome(kind=OutcomeKind.DONE, result=FixConflictResult.PLANNED)
    write_json(folders.make_out() / "outcome.json", forged)
    with pytest.raises(PhaseOutputError, match="names no result"):
        fix_conflict_phases.publish_phase(pull.store, client, folders, repo=REPO, pull=pull.number)
    assert pull.pushed() == pull.head

    ended = RunFolders(tmp_path / "ended")
    pull.store.add_label(pull.number, "owner/agent")
    refused = fix_conflict_phases.prepare_phase(
        pull.store, client, REPO, pull.number, head=None, folders=ended
    )
    assert refused is not None
    assert refused.result == FixConflictResult.REFUSED
    assert (
        fix_conflict_phases.publish_phase(pull.store, client, ended, repo=REPO, pull=pull.number)
        is None
    )


def test_a_timeout_of_tier_1_counts_the_round_and_pushes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`uv lock` runs out of time, which is no stop of the step: the error goes on. The round still
    counts, because `prepare` records it when it gives the round to the agent phase, so the caps
    hold, and nothing is pushed (#6703)."""
    pull = _pull_with_docs_conflict(tmp_path)
    _with_pull_request_code(monkeypatch, pull, timeout="lock")

    with pytest.raises(subprocess.TimeoutExpired) as raised:
        run_fix_conflict(pull.store, REPO, pull.number, confirm=True)

    assert raised.value.timeout == 1800

    item = pull.store.item(pull.number)
    assert item is not None
    record = item.job_record
    assert (record.get(FixConflictRecordKey.ROUNDS), record.get(FixConflictRecordKey.RESULT)) == (
        "1",
        FixConflictResult.FAILED.value,
    )
    assert pull.pushed() == pull.head


def test_a_head_that_moves_before_the_push_counts_the_round(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Another writer moves the head while the agent phase runs. `publish` refuses the push on
    the admission bounds, and the round that ran tier 1 still counts (#6703)."""
    pull = _pull_with_docs_conflict(tmp_path)
    _with_pull_request_code(monkeypatch, pull)
    statuses = _fake_github(monkeypatch, pull.status(), pull.upstream)
    agent = fix_conflict_phases.agent_phase

    def agent_then_move(folders: RunFolders) -> None:
        agent(folders)
        statuses.append(_pull_status("5" * 40, pull.branch))

    monkeypatch.setattr(fix_conflict_phases, "agent_phase", agent_then_move)

    report = run_fix_conflict(pull.store, REPO, pull.number, confirm=True)

    item = pull.store.item(pull.number)
    assert item is not None
    assert (report.result, "head moved" in report.reason) == (FixConflictResult.REFUSED, True)
    assert (pull.pushed(), item.job_record.get(FixConflictRecordKey.ROUNDS)) == (pull.head, "1")


def test_a_plan_on_a_host_with_no_app_gives_the_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, config: Callable[..., Path]
) -> None:
    """Without `--confirm` the round makes a plan and pushes nothing, so its clone needs no App:
    a host with no `service.github_app.slug` gets the plan (#6703)."""
    config(service={"github_app": {"slug": None}})
    pull = _pull_with_archive_conflict(tmp_path)
    ran = _with_pull_request_code(monkeypatch, pull)

    report = run_fix_conflict(pull.store, REPO, pull.number)

    assert (report.result, ran) == (FixConflictResult.PLANNED, [])


def _separate_phases(
    pull: _Pull, folders: RunFolders, between: Callable[[], None] = lambda: None
) -> FixConflictReport | None:
    """`prepare`, `agent` and `publish` as separate calls on one run folder, with `between` after
    the agent phase."""
    client = fix_conflict.get_github_session().client
    prepared = fix_conflict_phases.prepare_phase(
        pull.store, client, REPO, pull.number, head=pull.head, folders=folders
    )
    assert prepared is None
    fix_conflict_phases.agent_phase(folders)
    between()
    return fix_conflict_phases.publish_phase(
        pull.store, client, folders, repo=REPO, pull=pull.number
    )


def test_a_separate_publish_takes_no_cap_for_the_round_that_prepare_counted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The record holds 3 rounds, so `prepare` counts the fourth round, which the hard cap of 4
    rounds still admits. A separate `publish` checks no cap, and pushes the round."""
    pull = _pull_with_docs_conflict(tmp_path)
    _with_pull_request_code(monkeypatch, pull)
    fix_conflict.record_fix_conflict_marks(
        pull.store, pull.number, rounds=3, files=["a", "b", "c"], result=FixConflictResult.FAILED
    )

    report = _separate_phases(pull, RunFolders(tmp_path / "run"))

    assert report is not None
    assert (report.result, report.rounds) == (FixConflictResult.RESOLVED, 4)
    assert pull.pushed() == report.head != pull.head


def test_a_claim_before_a_separate_publish_is_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A person claims the item after the agent phase. A separate `publish` refuses the push
    (`before_push`), and the record holds the refusal and the round that `prepare` counted."""
    pull = _pull_with_docs_conflict(tmp_path)
    _with_pull_request_code(monkeypatch, pull)

    report = _separate_phases(
        pull,
        RunFolders(tmp_path / "run"),
        lambda: pull.store.add_label(pull.number, "owner/agent"),
    )

    item = pull.store.item(pull.number)
    assert report is not None
    assert item is not None
    assert (report.result, report.rounds) == (FixConflictResult.REFUSED, 1)
    record = item.job_record
    assert (record.get(FixConflictRecordKey.ROUNDS), record.get(FixConflictRecordKey.RESULT)) == (
        "1",
        FixConflictResult.REFUSED.value,
    )
    assert pull.pushed() == pull.head


@pytest.mark.parametrize("separate", [False, True], ids=["phase all", "separate phases"])
def test_a_claim_after_a_stop_of_the_agent_keeps_the_stop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, separate: bool
) -> None:
    """The agent phase stops on a conflict that no rule settles, and then a person claims the
    item. The round pushes nothing, so `publish` keeps the stop and the reason of the agent in
    both run modes: it checks the admission bounds only right before a push (#6703)."""
    pull = _pull_with_archive_conflict(tmp_path, spec_fix=True)
    _with_pull_request_code(monkeypatch, pull)

    def claim() -> None:
        pull.store.add_label(pull.number, "owner/agent")

    if separate:
        report = _separate_phases(pull, RunFolders(tmp_path / "run"), claim)
    else:
        agent = fix_conflict_phases.agent_phase

        def agent_then_claim(folders: RunFolders) -> None:
            agent(folders)
            claim()

        monkeypatch.setattr(fix_conflict_phases, "agent_phase", agent_then_claim)
        report = run_fix_conflict(pull.store, REPO, pull.number, confirm=True)

    item = pull.store.item(pull.number)
    assert report is not None
    assert item is not None
    assert (report.result, report.reason, report.rounds) == (
        FixConflictResult.STOPPED,
        _NOT_SETTLED,
        1,
    )
    assert item.job_record.get(FixConflictRecordKey.RESULT) == FixConflictResult.STOPPED.value
    assert pull.pushed() == pull.head
