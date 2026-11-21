"""Tests for the roadmap step `fix-conflict` (#5019).

Verifies:
- Dry-run sees 0 requests
- A person pull request is refused
- A person commit after bot push is refused
- An item with an owner label or human claim is refused
- Conflict on a release path stops with class conflict
- Archive-only conflict ends with clean push and 0 model requests
- Soft and hard caps hold
- Strict validation runs before push
- Without --confirm the step runs no code of the pull request and writes nothing
- A confirmed round pushes only to the URL of origin that the step read after its clone
"""

from __future__ import annotations

import json
import os
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
from devops_cli.roadmap.steps import fix_conflict
from devops_cli.roadmap.steps.fix_conflict import (
    FixConflictReport,
    FixConflictResult,
    check_merge_tree_conflict,
    dry_run_fix_conflict,
    fix_rebase_conflict,
    is_archive_path,
    is_generated_docs_path,
    is_lockfile_path,
    is_release_path,
    resolve_tier1,
    run_fix_conflict,
)
from devops_cli.roadmap.stores.store import FixConflictRecordKey
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

if TYPE_CHECKING:
    pass

pytestmark = pytest.mark.usefixtures("keyring_store")

REPO = "example/project"
BOT_USER = "devops-cli-service[bot]"
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


def test_conflict_on_release_path_stops_with_class_conflict(tmp_path: Path) -> None:
    """A conflict on a release path stops with class conflict."""
    store = InMemoryRoadmapStore(repo=REPO)
    num = store.seed_issue(title="feat: test", labels=("status/in-progress", "priority/p2-medium"))

    # Setup git repo
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    _git(repo_dir, "init", "-b", "main")
    _git(repo_dir, "config", "user.name", "Bot")
    _git(repo_dir, "config", "user.email", "bot@example.com")
    (repo_dir / CONST_CHANGELOG_FILENAME).write_text("Changelog v1\n", encoding="utf-8")
    _git(repo_dir, "add", "-A")
    _git(repo_dir, "commit", "-m", "init")

    _git(repo_dir, "checkout", "-b", BRANCH)
    (repo_dir / CONST_CHANGELOG_FILENAME).write_text(
        "Changelog v1\nBranch change\n", encoding="utf-8"
    )
    _git(repo_dir, "commit", "-am", "branch changelog")

    _git(repo_dir, "checkout", "main")
    (repo_dir / CONST_CHANGELOG_FILENAME).write_text(
        "Changelog v1\nMain change\n", encoding="utf-8"
    )
    _git(repo_dir, "commit", "-am", "main changelog")

    _git(repo_dir, "checkout", BRANCH)
    _git(repo_dir, "update-ref", "refs/remotes/origin/main", "main")
    subprocess.run([CONST_GIT_CLI, "-C", str(repo_dir), "rebase", "main"], capture_output=True)

    # Call fix_rebase_conflict
    resolved = fix_rebase_conflict(
        repo_dir,
        repo=REPO,
        item=num,
        default_branch="main",
        store=store,
    )
    assert resolved is False

    saved_item = store.item(num)
    assert saved_item is not None
    assert saved_item.job_record.get(FixConflictRecordKey.RESULT) == FixConflictResult.STOPPED.value
    assert saved_item.job_record.get(FixConflictRecordKey.ROUNDS) == "1"
    assert CONST_CHANGELOG_FILENAME in (saved_item.job_record.get(FixConflictRecordKey.FILES) or "")


def test_archive_only_conflict_ends_with_clean_push_and_zero_model_requests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An archive-only conflict ends with clean push and 0 model requests."""
    # Setup origin and local repo
    origin_dir = tmp_path / "origin.git"
    origin_dir.mkdir()
    subprocess.run([CONST_GIT_CLI, "init", "--bare", "-b", "main", str(origin_dir)], check=True)

    clone_dir = tmp_path / "clone"
    subprocess.run([CONST_GIT_CLI, "clone", str(origin_dir), str(clone_dir)], check=True)
    _git(clone_dir, "config", "user.name", "Bot[bot]")
    _git(clone_dir, "config", "user.email", "bot@example.com")

    # Initial main commit
    specs_dir = clone_dir / "openspec" / "specs" / "test-cap"
    specs_dir.mkdir(parents=True, exist_ok=True)
    (specs_dir / "spec.md").write_text(
        "# Test Spec\n\n## Requirements\nInitial req.\n", encoding="utf-8"
    )
    _git(clone_dir, "add", "-A")
    _git(clone_dir, "commit", "-m", "chore: initial specs")
    _git(clone_dir, "push", "origin", "main")

    # Store and issue
    store = InMemoryRoadmapStore(repo=REPO)
    num = store.seed_issue(title="feat: test", labels=("status/in-progress", "priority/p2-medium"))

    # Branch with active change and archive commit
    _git(clone_dir, "checkout", "-b", BRANCH)
    change_dir = clone_dir / "openspec" / "changes" / f"{num}-test-cap"
    change_dir.mkdir(parents=True, exist_ok=True)
    (change_dir / "tasks.md").write_text("- [x] task done\n", encoding="utf-8")
    _git(clone_dir, "add", "-A")
    _git(clone_dir, "commit", "-m", f"feat: implement {num}")

    # Archive commit
    archived_dir = clone_dir / "openspec" / "changes" / "archive" / f"2026-11-16-{num}-test-cap"
    archived_dir.mkdir(parents=True, exist_ok=True)
    shutil.move(str(change_dir), str(archived_dir / "change"))
    (specs_dir / "spec.md").write_text(
        f"# Test Spec\n\n## Requirements\nInitial req.\nAdded req {num}.\n", encoding="utf-8"
    )
    _git(clone_dir, "add", "-A")
    _git(clone_dir, "commit", "-m", f"docs(openspec): archive the change (#{num})")
    _git(clone_dir, "push", "origin", BRANCH)

    # Meanwhile main adds another spec change that conflicts
    _git(clone_dir, "checkout", "main")
    (specs_dir / "spec.md").write_text(
        "# Test Spec\n\n## Requirements\nInitial req.\nMain req concurrent.\n", encoding="utf-8"
    )
    _git(clone_dir, "commit", "-am", "chore: concurrent spec update")
    _git(clone_dir, "push", "origin", "main")

    # Now in branch, rebase fails on archive/specs
    _git(clone_dir, "checkout", BRANCH)
    _git(clone_dir, "fetch", "origin")
    subprocess.run(
        [CONST_GIT_CLI, "-C", str(clone_dir), "rebase", "origin/main"], capture_output=True
    )

    # Mock openspec archive and validate
    monkeypatch.setattr(fix_conflict, "validate_strict_specs", lambda cwd: True)

    def fake_subprocess(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        kwargs.pop("quiet", None)
        if "docs" in cmd and "generate" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="docs generated", stderr="")
        if "openspec" in cmd and "archive" in cmd:
            # recreate archive folder
            arch = clone_dir / "openspec" / "changes" / "archive" / f"2026-11-16-{num}-test-cap"
            arch.mkdir(parents=True, exist_ok=True)
            active = clone_dir / "openspec" / "changes" / f"{num}-test-cap"
            if active.exists():
                shutil.rmtree(active, ignore_errors=True)
            return subprocess.CompletedProcess(cmd, 0, stdout="archived", stderr="")
        return subprocess.run(cmd, capture_output=True, text=True, **kwargs)

    monkeypatch.setattr(fix_conflict, "run_subprocess", fake_subprocess)

    resolved = fix_rebase_conflict(
        clone_dir,
        repo=REPO,
        item=num,
        default_branch="main",
        store=store,
    )
    assert resolved is True

    # Rebase should be clean now
    status = _git(clone_dir, "status", "--porcelain")
    assert status == ""
    head_msg = _git(clone_dir, "log", "-1", "--format=%s")
    assert f"archive the change (#{num})" in head_msg


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
    err = fix_conflict._check_admission_bounds(status, None, expected_head="222222")
    assert err is not None
    assert "head moved" in err

    # PR holds owner label
    err2 = fix_conflict._check_admission_bounds(status, None)
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
    err3 = fix_conflict._check_admission_bounds(status_clean, item)
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

    assert fix_conflict._check_admission_bounds(status, store.item(number)) is None


def test_conflict_caps_helper() -> None:
    from devops_cli.config.settings import load_settings

    settings = load_settings().roadmap.fix_conflict

    # Hard cap
    err = fix_conflict._check_conflict_caps(4, ["a.py"], ["a.py"], settings)
    assert err is not None
    assert "Hard cap reached" in err

    # Soft cap without reduction
    err2 = fix_conflict._check_conflict_caps(2, ["a.py", "b.py"], ["a.py"], settings)
    assert err2 is not None
    assert "Soft cap reached" in err2

    # Soft cap with reduction
    err3 = fix_conflict._check_conflict_caps(2, ["a.py"], ["a.py", "b.py"], settings)
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


def test_no_human_commit_after_bot(tmp_path: Path) -> None:
    repo = tmp_path / "human_repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Bot[bot]")
    _git(repo, "config", "user.email", "bot@example.com")
    (repo / "file.txt").write_text("v1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "init")

    _git(repo, "checkout", "-b", "feat/branch")
    (repo / "file.txt").write_text("v2\n", encoding="utf-8")
    _git(repo, "commit", "-am", "bot update")

    # Clean bot check
    assert fix_conflict._check_no_human_commit_after_bot(repo, "main", "feat/branch") is True

    # Human commits
    _git(repo, "config", "user.name", "Alice Human")
    _git(repo, "config", "user.email", "alice@example.com")
    (repo / "file.txt").write_text("v3\n", encoding="utf-8")
    _git(repo, "commit", "-am", "human edit")

    assert fix_conflict._check_no_human_commit_after_bot(repo, "main", "feat/branch") is False


def test_resolve_tier1_docs_and_lockfile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "tier1_docs"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Bot[bot]")
    _git(repo, "config", "user.email", "bot@example.com")
    (repo / "docs").mkdir()
    (repo / "docs" / "CLI_REFERENCE.md").write_text("# Docs v1\n", encoding="utf-8")
    (repo / "uv.lock").write_text("# lock v1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "init")

    _git(repo, "checkout", "-b", "feat/branch")
    (repo / "docs" / "CLI_REFERENCE.md").write_text("# Docs v1\nBranch doc\n", encoding="utf-8")
    (repo / "uv.lock").write_text("# lock v1\nBranch lock\n", encoding="utf-8")
    _git(repo, "commit", "-am", "branch update")

    _git(repo, "checkout", "main")
    (repo / "docs" / "CLI_REFERENCE.md").write_text("# Docs v1\nMain doc\n", encoding="utf-8")
    (repo / "uv.lock").write_text("# lock v1\nMain lock\n", encoding="utf-8")
    _git(repo, "commit", "-am", "main update")

    _git(repo, "checkout", "feat/branch")
    subprocess.run([CONST_GIT_CLI, "-C", str(repo), "rebase", "main"], capture_output=True)

    def fake_sub(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        kwargs.pop("quiet", None)
        if "docs" in cmd and "generate" in cmd:
            (repo / "docs" / "CLI_REFERENCE.md").write_text(
                "# Docs regenerated\n", encoding="utf-8"
            )
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if "lock" in cmd:
            (repo / "uv.lock").write_text("# lock regenerated\n", encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        return subprocess.run(cmd, capture_output=True, text=True, **kwargs)

    monkeypatch.setattr(fix_conflict, "run_subprocess", fake_sub)

    assert resolve_tier1(repo, 42) is None
    assert _git(repo, "status", "--porcelain") == ""


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


def test_run_fix_conflict_scenarios(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    origin_dir = tmp_path / "origin.git"
    origin_dir.mkdir()
    subprocess.run([CONST_GIT_CLI, "init", "--bare", "-b", "main", str(origin_dir)], check=True)

    clone_dir = tmp_path / "local"
    subprocess.run([CONST_GIT_CLI, "clone", str(origin_dir), str(clone_dir)], check=True)
    _git(clone_dir, "config", "user.name", "Bot[bot]")
    _git(clone_dir, "config", "user.email", "bot@example.com")

    (clone_dir / "base.txt").write_text("v1\n", encoding="utf-8")
    _git(clone_dir, "add", "-A")
    _git(clone_dir, "commit", "-m", "chore: base")
    _git(clone_dir, "push", "origin", "main")

    store = InMemoryRoadmapStore(repo=REPO)
    num = store.seed_issue(title="feat: item", labels=("status/in-progress", "priority/p2-medium"))

    # Branch 1: clean branch (no conflict)
    branch_clean = f"feat/{num}-clean"
    _git(clone_dir, "checkout", "-b", branch_clean)
    (clone_dir / "new_file.txt").write_text("clean\n", encoding="utf-8")
    _git(clone_dir, "add", "-A")
    _git(clone_dir, "commit", "-m", "clean commit")
    _git(clone_dir, "push", "origin", branch_clean)
    clean_sha = _git(clone_dir, "rev-parse", "HEAD")

    class FakeClient:
        def __init__(self, sha: str, branch: str) -> None:
            self._sha = sha
            self._branch = branch

        def get_pull_status(self, repo: str, pull: int) -> PullStatus:
            return PullStatus.model_validate(
                {
                    "state": "open",
                    "draft": False,
                    "head": {"ref": self._branch, "sha": self._sha},
                    "base": {"ref": "main"},
                    "user": {"login": BOT_USER},
                    "labels": [],
                }
            )

    class FakeSession:
        def __init__(self, sha: str, branch: str) -> None:
            self.client = FakeClient(sha, branch)

    # 1. No conflict scenario
    monkeypatch.setattr(
        fix_conflict, "get_github_session", lambda: FakeSession(clean_sha, branch_clean)
    )
    rep = run_fix_conflict(store, REPO, num, source=clone_dir)
    assert rep.result == FixConflictResult.NO_CONFLICT

    # 2. Human commit scenario
    _git(clone_dir, "config", "user.name", "Alice Human")
    (clone_dir / "human.txt").write_text("human\n", encoding="utf-8")
    _git(clone_dir, "add", "-A")
    _git(clone_dir, "commit", "-m", "human commit")
    _git(clone_dir, "push", "origin", branch_clean)
    human_sha = _git(clone_dir, "rev-parse", "HEAD")

    monkeypatch.setattr(
        fix_conflict, "get_github_session", lambda: FakeSession(human_sha, branch_clean)
    )
    rep_human = run_fix_conflict(store, REPO, num, source=clone_dir)
    assert rep_human.result == FixConflictResult.REFUSED
    assert "Human commit detected" in rep_human.reason

    # 3. Code conflict scenario: a plan without --confirm, and a stop of Tier 1 with it
    _git(clone_dir, "checkout", "main")
    (clone_dir / "base.txt").write_text("main update\n", encoding="utf-8")
    _git(clone_dir, "commit", "-am", "main conflict update")
    _git(clone_dir, "push", "origin", "main")

    _git(clone_dir, "checkout", "-b", f"feat/{num}-code-conflict", "HEAD~1")
    _git(clone_dir, "config", "user.name", "Bot[bot]")
    (clone_dir / "base.txt").write_text("branch conflict update\n", encoding="utf-8")
    _git(clone_dir, "commit", "-am", "branch code update")
    _git(clone_dir, "push", "origin", f"feat/{num}-code-conflict")
    code_sha = _git(clone_dir, "rev-parse", "HEAD")

    monkeypatch.setattr(
        fix_conflict,
        "get_github_session",
        lambda: FakeSession(code_sha, f"feat/{num}-code-conflict"),
    )
    rep_plan = run_fix_conflict(store, REPO, num, source=clone_dir, confirm=False)
    assert (rep_plan.result, rep_plan.files) == (FixConflictResult.PLANNED, ("base.txt",))
    assert rep_plan.reason.startswith("Plan: stop, because tier 1 settles only")
    rep_code = run_fix_conflict(store, REPO, num, source=clone_dir, confirm=True)
    assert rep_code.result == FixConflictResult.STOPPED
    assert "could not be resolved by Tier 1" in rep_code.reason

    # 4. Strict specs failure scenario
    item = store.item(num)
    assert item is not None
    item.job_record.clear()

    def fake_resolve_tier1(cwd: Path, *args: Any, **kwargs: Any) -> str | None:
        (cwd / "base.txt").write_text("resolved\n", encoding="utf-8")
        _git(cwd, "add", "-A")
        proc = subprocess.run(
            [CONST_GIT_CLI, "-C", str(cwd), "rebase", "--continue"],
            capture_output=True,
            text=True,
            env=dict(os.environ, GIT_EDITOR="true"),
        )
        return None if proc.returncode == 0 else "not settled"

    monkeypatch.setattr(fix_conflict, "resolve_tier1", fake_resolve_tier1)
    monkeypatch.setattr(fix_conflict, "validate_strict_specs", lambda *args: False)
    rep_spec = run_fix_conflict(store, REPO, num, source=clone_dir, confirm=True)
    assert rep_spec.result == FixConflictResult.FAILED
    assert "strict failed" in rep_spec.reason

    # 5. Clean Tier 1 resolution with lease push; the failed round of 4 counted too
    store.set_marks(item, {FixConflictRecordKey.ROUNDS: "0"})
    monkeypatch.setattr(fix_conflict, "validate_strict_specs", lambda *args: True)
    rep_ok = run_fix_conflict(store, REPO, num, source=clone_dir, confirm=True)
    assert rep_ok.result == FixConflictResult.RESOLVED


def test_fix_conflict_internal_helpers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # 1. _git failure raises GitOperationError
    with pytest.raises(GitOperationError, match="git status failed"):
        fix_conflict._git(tmp_path, "status")

    # 2. is_release_path diff hunk: only the version line of pyproject.toml is release metadata
    assert is_release_path("pyproject.toml", '-  version = "1.2.3"')
    assert not is_release_path("some/file.py", '+__version__ = "1.2.3"')
    assert not is_release_path("some/file.py", '+version = "1.2.3"')
    assert not is_release_path("some/file.py", "+something_else = 1")

    # 3. _record_fix_conflict_marks with None store or None item
    fix_conflict._record_fix_conflict_marks(
        None, None, rounds=1, files=[], result=FixConflictResult.RESOLVED
    )
    store = InMemoryRoadmapStore(repo=REPO)
    fix_conflict._record_fix_conflict_marks(
        store, None, rounds=1, files=[], result=FixConflictResult.RESOLVED
    )

    # 4. _read_item_conflict_state with None or invalid json
    assert fix_conflict._read_item_conflict_state(None) == (0, [])
    num = store.seed_issue(title="feat: item", labels=("status/in-progress", "priority/p2-medium"))
    item = store.item(num)
    assert item is not None
    item.job_record[FixConflictRecordKey.FILES] = "not-json"
    assert fix_conflict._read_item_conflict_state(item) == (0, [])

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

    # 6. _check_admission_bounds with claimed_by and owner label
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
    err = fix_conflict._check_admission_bounds(status, item_owner)
    assert err
    assert "holds owner label" in err

    num_claimed = store.seed_issue(title="feat: item claimed", labels=("priority/p2-medium",))
    item_claimed = store.item(num_claimed)
    assert item_claimed is not None
    # Simulate a human claim
    item_claimed = item_claimed.model_copy(update={"owner": "human"})

    err2 = fix_conflict._check_admission_bounds(status, item_claimed)
    assert err2
    assert "claimed by" in err2


def test_a_clone_that_fails_ends_the_round(monkeypatch: pytest.MonkeyPatch) -> None:
    """With no `source`, the step clones the repository into a new folder of the run
    (`ensure_checkout`). A clone that fails ends the round with `failed`."""
    status = PullStatus.model_validate(
        {
            "state": "open",
            "draft": False,
            "head": {"ref": BRANCH, "sha": "111111"},
            "base": {"ref": CONST_GIT_MAIN_BRANCH},
            "user": {"login": BOT_USER},
            "labels": [],
        }
    )

    class FakeClient:
        def get_pull_status(self, repo: str, pull: int) -> PullStatus:
            return status

    class FakeSession:
        client = FakeClient()

    def refused(repo: str, data_dir: Path, *args: Any, **kwargs: Any) -> Path:
        assert data_dir.is_dir()
        raise GitOperationError("clone failed", operation="test")

    monkeypatch.setattr(fix_conflict, "get_github_session", lambda: FakeSession())
    monkeypatch.setattr(fix_conflict, "ensure_checkout", refused)

    report = run_fix_conflict(InMemoryRoadmapStore(repo=REPO), REPO, 42)

    assert (report.result, report.reason) == (FixConflictResult.FAILED, "clone failed")


def test_fix_rebase_conflict_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = InMemoryRoadmapStore(repo=REPO)
    num = store.seed_issue(title="feat: item", labels=("status/in-progress", "priority/p2-medium"))

    def call() -> bool:
        return fix_rebase_conflict(
            tmp_path, repo=REPO, item=num, default_branch="main", store=store
        )

    # 1. No conflicts
    monkeypatch.setattr(fix_conflict, "conflicted_files", lambda cwd: [])
    assert call() is False

    # 2. Release path conflict
    monkeypatch.setattr(fix_conflict, "conflicted_files", lambda cwd: [CONST_CHANGELOG_FILENAME])
    monkeypatch.setattr(fix_conflict, "_git", lambda cwd, *args: "")
    monkeypatch.setattr(fix_conflict, "release_conflict", lambda cwd, base, head: True)
    assert call() is False

    # 3. Resolved but validate_strict_specs fails
    monkeypatch.setattr(fix_conflict, "release_conflict", lambda cwd, base, head: False)
    monkeypatch.setattr(fix_conflict, "resolve_tier1", lambda cwd, item: None)
    monkeypatch.setattr(fix_conflict, "validate_strict_specs", lambda cwd: False)
    assert call() is False

    # 4. Resolved and validate_strict_specs succeeds
    monkeypatch.setattr(fix_conflict, "validate_strict_specs", lambda cwd: True)
    assert call() is True

    # 5. Not resolved
    monkeypatch.setattr(fix_conflict, "resolve_tier1", lambda cwd, item: "not settled")
    assert call() is False


# Tier 1 runs code of the checkout of the pull request: `uv run devops docs generate` and `uv lock`
# start the entry point of the project and its build hooks. The double of the `uv` process writes
# one of these into the clone, as such code can.
_WRITTEN = ("pre-push hook", "remote.origin.pushurl", "remote.origin.receivepack", "url.insteadOf")
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
    _git(clone, "config", "user.name", "Bot[bot]")
    _git(clone, "config", "user.email", "bot@example.com")


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


def _with_pull_request_code(
    monkeypatch: pytest.MonkeyPatch, pull: _Pull, written: str | None = None, *, valid: bool = True
) -> list[list[str]]:
    """Run the step against `pull`: GitHub gives its status, each `uv` process is the code of the
    pull request, `openspec archive` moves the change folder and `openspec validate` gives
    `valid`. git runs for real through the process runner, which gives the token to each git child
    that reaches a remote. The list holds each `uv` process."""
    ran: list[list[str]] = []
    status = pull.status()

    class FakeClient:
        def get_pull_status(self, repo: str, number: int) -> PullStatus:
            return status

    class FakeSession:
        client = FakeClient()

    def run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if cmd[0] == BIN_UV:
            ran.append(cmd)
            _write_into_clone(pull, Path(kwargs["cwd"]), written)
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if cmd[0] == BIN_OPENSPEC:
            if "archive" in cmd:
                changes = Path(kwargs["cwd"]) / "openspec" / "changes"
                active = changes / f"{pull.number}-test-cap"
                shutil.move(active, changes / "archive" / f"2026-11-21-{pull.number}-test-cap")
            return subprocess.CompletedProcess(cmd, 0 if valid else 1, stdout="", stderr="")
        return run_subprocess(cmd, **kwargs)

    monkeypatch.setattr(fix_conflict, "get_github_session", lambda: FakeSession())
    monkeypatch.setattr(fix_conflict, "run_subprocess", run)
    return ran


def test_without_confirm_the_step_runs_no_code_of_the_pull_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without --confirm, as on a workstation, the step finds the conflict and returns its plan,
    which names the runner Job. It runs no fixer of tier 1, pushes nothing and writes no record."""
    pull = _pull_with_archive_conflict(tmp_path)
    ran = _with_pull_request_code(monkeypatch, pull, "pre-push hook")

    report = run_fix_conflict(pull.store, REPO, pull.number, source=pull.clone)

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
    write a hook or a git setting into the clone. The push still goes through `OriginGit` to the URL
    of origin that the step read after its clone, before that code ran."""
    config(roadmap={"implement": {"in_runner": True}})
    pull = _pull_with_archive_conflict(tmp_path)
    ran = _with_pull_request_code(monkeypatch, pull, written)

    report = run_fix_conflict(pull.store, REPO, pull.number, source=pull.clone, confirm=True)

    assert ran
    assert pull.written() == []
    assert report.result == FixConflictResult.RESOLVED
    assert pull.pushed() == report.head != pull.head


def test_an_archive_commit_that_is_not_the_tip_is_dropped_and_written_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """At the stop on the archive commit, the round runs `git rebase --skip`, so HEAD stays on the
    head branch and the commit after the archive commit stays. After the rebase it archives the
    change again, in a commit of its own on the tip."""
    pull = _pull_with_archive_conflict(tmp_path, after=True)
    _with_pull_request_code(monkeypatch, pull)

    report = run_fix_conflict(pull.store, REPO, pull.number, source=pull.clone, confirm=True)

    assert (report.result, report.reason) == (FixConflictResult.RESOLVED, "")
    assert pull.pushed_file("src/fix.py") == "F = 1\n"
    assert pull.pushed_file("src/a.py") == "A = 1\n"
    assert pull.pushed_file(f"openspec/changes/archive/2026-11-21-{pull.number}-test-cap/tasks.md")
    subject = _git(pull.upstream, "log", "-1", "--format=%s", pull.branch)
    assert subject == f"docs(openspec): archive the change (#{pull.number})"


def test_an_archive_commit_that_holds_other_paths_stops_the_round(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The round drops a commit only when each of its paths is an OpenSpec path or a generated
    document. A commit that also holds code, such as one squashed commit, stops the round, and the
    head branch does not change."""
    pull = _pull_with_archive_conflict(tmp_path, squashed=True)
    ran = _with_pull_request_code(monkeypatch, pull)

    report = run_fix_conflict(pull.store, REPO, pull.number, source=pull.clone, confirm=True)

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

    report = run_fix_conflict(pull.store, REPO, pull.number, source=pull.clone, confirm=True)

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

    plan = run_fix_conflict(pull.store, REPO, pull.number, source=pull.clone)
    report = run_fix_conflict(pull.store, REPO, pull.number, source=pull.clone, confirm=True)

    assert plan.reason.startswith("Plan: drop the archive commit of the item")
    assert (report.result, report.reason) == (FixConflictResult.RESOLVED, "")
    subject = _git(pull.upstream, "log", "-1", "--format=%s", pull.branch)
    assert subject == f"docs(openspec): archive the change (#{pull.number})"


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

    report = run_fix_conflict(pull.store, REPO, pull.number, source=pull.clone, confirm=True)

    assert (report.result, report.reason) == (FixConflictResult.RESOLVED, "")
    assert (pull.pushed_file(old), pull.pushed_file("src/feature.py")) == ("", "A = 1\n")


def test_a_round_that_git_refuses_stops_and_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A git call of tier 1 that fails ends the round as a stop: the rebase is aborted, the stop is
    recorded, and the head branch does not change."""
    pull = _pull_with_docs_conflict(tmp_path)
    _with_pull_request_code(monkeypatch, pull)

    def refused(cwd: Path, *args: Any) -> str | None:
        raise GitOperationError("git checkout failed", operation="test")

    monkeypatch.setattr(fix_conflict, "resolve_tier1", refused)

    report = run_fix_conflict(pull.store, REPO, pull.number, source=pull.clone, confirm=True)

    assert (report.result, report.reason) == (FixConflictResult.STOPPED, "git checkout failed")
    assert pull.pushed() == pull.head
    assert not (pull.clone / ".git" / "rebase-merge").exists()
    item = pull.store.item(pull.number)
    assert item is not None
    assert item.job_record.get(FixConflictRecordKey.ROUNDS) == "1"


def test_a_skip_that_git_refuses_stops_the_round(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each `--skip` or `--continue` moves the rebase on or stops the round. A call that fails and
    leaves the rebase on the same commit is a stop of git, which the round records."""
    pull = _pull_with_archive_conflict(tmp_path)
    _with_pull_request_code(monkeypatch, pull)
    code = fix_conflict.run_subprocess
    skips: list[int] = []

    def refused(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if cmd[-2:] == ["rebase", "--skip"]:
            skips.append(1)
            if len(skips) > 3:
                raise RuntimeError("the round skips again and again")
            return subprocess.CompletedProcess(cmd, 128, "", "fatal: could not discard changes")
        return code(cmd, **kwargs)

    monkeypatch.setattr(fix_conflict, "run_subprocess", refused)

    report = run_fix_conflict(pull.store, REPO, pull.number, source=pull.clone, confirm=True)

    assert (report.result, report.reason) == (
        FixConflictResult.STOPPED,
        "git rebase --skip failed: fatal: could not discard changes",
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

    report = run_fix_conflict(pull.store, REPO, pull.number, source=pull.clone, confirm=True)

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

    report = run_fix_conflict(pull.store, REPO, pull.number, source=pull.clone, confirm=True)

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

    report = run_fix_conflict(pull.store, REPO, pull.number, source=pull.clone, confirm=True)

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

    report = run_fix_conflict(pull.store, REPO, pull.number, source=pull.clone, confirm=True)

    assert (report.result, report.reason) == (
        FixConflictResult.FAILED,
        "The rebase left no commit past origin/main",
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

    report = run_fix_conflict(pull.store, REPO, pull.number, source=pull.clone, confirm=True)

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

    plan = run_fix_conflict(pull.store, REPO, pull.number, source=pull.clone)
    done = run_fix_conflict(pull.store, REPO, pull.number, source=pull.clone, confirm=True)

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

    plan = run_fix_conflict(pull.store, REPO, pull.number, source=pull.clone)
    done = run_fix_conflict(pull.store, REPO, pull.number, source=pull.clone, confirm=True)

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

    plan = run_fix_conflict(pull.store, REPO, pull.number, source=pull.clone)
    done = run_fix_conflict(pull.store, REPO, pull.number, source=pull.clone, confirm=True)

    assert plan.reason.startswith("Plan: stop on the release path")
    assert (done.result, done.reason) == (FixConflictResult.STOPPED, "Conflict on a release path")
    assert (ran, pull.pushed()) == ([], pull.head)


def test_a_rebase_that_stops_for_another_cause_stops_the_round_and_pushes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A rebase that fails with no conflicted file is no settled conflict. Here git refuses the
    commit of the first, clean pick, because the identity of the clone is empty, so the rebase
    stops on the tip of main. The round stops, records the stop and pushes nothing."""
    pull = _pull_with_docs_conflict(tmp_path, clean_first=True)
    _git(pull.clone, "config", "user.name", "")
    _git(pull.clone, "config", "user.email", "")
    _with_pull_request_code(monkeypatch, pull)

    report = run_fix_conflict(pull.store, REPO, pull.number, source=pull.clone, confirm=True)

    assert pull.pushed() == pull.head
    assert report.result == FixConflictResult.STOPPED
    assert report.reason.startswith("The rebase failed with no conflicted file")
    item = pull.store.item(pull.number)
    assert item is not None
    assert item.job_record.get(FixConflictRecordKey.RESULT) == FixConflictResult.STOPPED.value


def _stopped_implement_rebase(tmp_path: Path) -> tuple[Path, str]:
    """A checkout of the implement job: two commits of its groups past main, whose generated
    document conflicts with main, and the rebase onto `origin/main` stopped. The tip before it."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _bot(repo)
    _commit_files(repo, {_DOCS: "# v1\n"}, "chore: base")
    _git(repo, "checkout", "-q", "-b", "feat/branch")
    _commit_files(repo, {_DOCS: "# v1\nbranch\n", "src/feature.py": "A = 1\n"}, "feat: group 1")
    _commit_files(repo, {"src/second.py": "B = 2\n"}, "feat: group 2")
    tip = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "main")
    _commit_files(repo, {_DOCS: "# v1\nmain\n"}, "chore: main")
    _git(repo, "update-ref", "refs/remotes/origin/main", "main")
    _git(repo, "checkout", "-q", "feat/branch")
    subprocess.run([CONST_GIT_CLI, "-C", str(repo), "rebase", "origin/main"], capture_output=True)
    return repo, tip


def test_a_tier_1_round_that_cannot_generate_again_stops_the_rebase_of_the_implement_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When `devops docs generate` fails after tier 1 took the default branch for the conflicted
    document, `fix_rebase_conflict` returns false and records the stop, so the implement job stops
    the item with the class `conflict`."""
    store = InMemoryRoadmapStore(repo=REPO)
    num = store.seed_issue(title="feat: item", labels=("status/in-progress", "priority/p2-medium"))
    repo, _ = _stopped_implement_rebase(tmp_path)

    def run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if cmd[0] == BIN_UV:
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="generate failed")
        return run_subprocess(cmd, **kwargs)

    monkeypatch.setattr(fix_conflict, "run_subprocess", run)

    assert (
        fix_rebase_conflict(repo, repo=REPO, item=num, default_branch="main", store=store) is False
    )
    item = store.item(num)
    assert item is not None
    assert item.job_record.get(FixConflictRecordKey.RESULT) == FixConflictResult.STOPPED.value


def test_a_timeout_of_tier_1_gives_the_implement_branch_back_its_tip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Any error of a round, also a timeout of `devops docs generate`, gives the implement branch
    back its tip and records the round before the error goes on to the job."""
    store = InMemoryRoadmapStore(repo=REPO)
    num = store.seed_issue(title="feat: item", labels=("status/in-progress", "priority/p2-medium"))
    item = store.item(num)
    assert item is not None
    store.set_marks(item, {FixConflictRecordKey.ROUNDS: "3"})
    repo, tip = _stopped_implement_rebase(tmp_path)

    def run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if cmd[0] == BIN_UV:
            raise subprocess.TimeoutExpired(cmd, 1800)
        return run_subprocess(cmd, **kwargs)

    monkeypatch.setattr(fix_conflict, "run_subprocess", run)

    with pytest.raises(subprocess.TimeoutExpired, match="timed out after 1800 seconds"):
        fix_rebase_conflict(repo, repo=REPO, item=num, default_branch="main", store=store)

    assert (_git(repo, "symbolic-ref", "HEAD"), _git(repo, "rev-parse", "HEAD")) == (
        "refs/heads/feat/branch",
        tip,
    )
    record = store.item(num)
    assert record is not None
    assert (
        record.job_record.get(FixConflictRecordKey.ROUNDS),
        record.job_record.get(FixConflictRecordKey.RESULT),
    ) == ("4", FixConflictResult.FAILED.value)


def test_a_failed_round_gives_the_implement_branch_back_its_tip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tier 1 settles the rebase of the implement job, and `openspec validate` then fails. The
    branch gets back the tip from before the rebase, with each commit of its groups, and not the
    tip of main."""
    repo, tip = _stopped_implement_rebase(tmp_path)

    def run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if cmd[0] in (BIN_UV, BIN_OPENSPEC):
            return subprocess.CompletedProcess(cmd, int(cmd[0] == BIN_OPENSPEC), "", "")
        return run_subprocess(cmd, **kwargs)

    monkeypatch.setattr(fix_conflict, "run_subprocess", run)

    assert fix_rebase_conflict(repo, repo=REPO, item=1, default_branch="main") is False
    assert _git(repo, "rev-parse", "feat/branch") == tip


def test_a_git_failure_in_the_implement_rebase_gives_back_the_tip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A git call of tier 1 that fails in the rebase of the implement job ends the round: the rebase
    is aborted, the branch is at its tip from before the rebase, and the stop is recorded."""
    store = InMemoryRoadmapStore(repo=REPO)
    num = store.seed_issue(title="feat: item", labels=("status/in-progress", "priority/p2-medium"))
    repo, tip = _stopped_implement_rebase(tmp_path)

    def refused(cwd: Path, *args: Any) -> str | None:
        raise GitOperationError("git checkout failed", operation="test")

    monkeypatch.setattr(fix_conflict, "resolve_tier1", refused)

    assert (
        fix_rebase_conflict(repo, repo=REPO, item=num, default_branch="main", store=store) is False
    )
    assert (_git(repo, "symbolic-ref", "HEAD"), _git(repo, "rev-parse", "HEAD")) == (
        "refs/heads/feat/branch",
        tip,
    )
    item = store.item(num)
    assert item is not None
    assert item.job_record.get(FixConflictRecordKey.RESULT) == FixConflictResult.STOPPED.value


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
    assert fix_conflict._plan_reason(conflicts, mode, release).startswith(plan)
