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
- Each fetch and push goes to the URL of origin that the step read after its clone, with no hook
  and no setting of the clone
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
from devops_cli.exceptions.roadmap import GitSettingsError
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

    resolved = resolve_tier1(repo, 42, "main", ["docs/CLI_REFERENCE.md", "uv.lock"])
    assert resolved is True
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
    rep_code = run_fix_conflict(store, REPO, num, source=clone_dir, confirm=True)
    assert rep_code.result == FixConflictResult.STOPPED
    assert "could not be resolved by Tier 1" in rep_code.reason

    # 4. Strict specs failure scenario
    item = store.item(num)
    assert item is not None
    item.job_record.clear()

    def fake_resolve_tier1(cwd: Path, *args: Any, **kwargs: Any) -> bool:
        (cwd / "base.txt").write_text("resolved\n", encoding="utf-8")
        _git(cwd, "add", "-A")
        proc = subprocess.run(
            [CONST_GIT_CLI, "-C", str(cwd), "rebase", "--continue"],
            capture_output=True,
            text=True,
            env=dict(os.environ, GIT_EDITOR="true"),
        )
        return proc.returncode == 0

    monkeypatch.setattr(fix_conflict, "resolve_tier1", fake_resolve_tier1)
    monkeypatch.setattr(fix_conflict, "validate_strict_specs", lambda *args: False)
    rep_spec = run_fix_conflict(store, REPO, num, source=clone_dir, confirm=True)
    assert rep_spec.result == FixConflictResult.FAILED
    assert "strict failed" in rep_spec.reason

    # 5. Clean Tier 1 resolution with lease push
    item.job_record.clear()
    monkeypatch.setattr(fix_conflict, "validate_strict_specs", lambda *args: True)
    rep_ok = run_fix_conflict(store, REPO, num, source=clone_dir, confirm=True)
    assert rep_ok.result == FixConflictResult.RESOLVED


def test_fix_conflict_internal_helpers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # 1. _git failure raises GitOperationError
    with pytest.raises(GitOperationError, match="git status failed"):
        fix_conflict._git(tmp_path, "status")

    # 2. is_release_path diff hunk
    assert is_release_path("some/file.py", '+__version__ = "1.2.3"')
    assert is_release_path("some/file.py", '+version = "1.2.3"')
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


def test_fix_conflict_source_cloning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # 1. Failure to clone
    monkeypatch.setattr(
        fix_conflict,
        "run_subprocess",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            [], 1, stdout="", stderr="clone failed"
        ),
    )
    with pytest.raises(GitOperationError, match="Failed to clone repository"):
        fix_conflict._clone_or_reuse_source("owner/repo", None)

    # 2. Success cloning
    monkeypatch.setattr(
        fix_conflict,
        "run_subprocess",
        lambda *args, **kwargs: subprocess.CompletedProcess([], 0, stdout="cloned", stderr=""),
    )
    worktree, temp_dir = fix_conflict._clone_or_reuse_source("owner/repo", None)
    assert temp_dir is not None
    assert worktree == temp_dir / "repo"
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_fix_rebase_conflict_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = InMemoryRoadmapStore(repo=REPO)
    num = store.seed_issue(title="feat: item", labels=("status/in-progress", "priority/p2-medium"))

    # 1. No conflicts
    monkeypatch.setattr(fix_conflict, "conflicted_files", lambda cwd: [])
    assert (
        fix_rebase_conflict(tmp_path, repo=REPO, item=num, default_branch="main", store=store)
        is False
    )

    # 2. Release path conflict
    monkeypatch.setattr(fix_conflict, "conflicted_files", lambda cwd: [CONST_CHANGELOG_FILENAME])
    monkeypatch.setattr(fix_conflict, "_has_release_path_conflict", lambda cwd, c: True)
    assert (
        fix_rebase_conflict(tmp_path, repo=REPO, item=num, default_branch="main", store=store)
        is False
    )

    # 3. Resolved but validate_strict_specs fails
    monkeypatch.setattr(fix_conflict, "_has_release_path_conflict", lambda cwd, c: False)
    monkeypatch.setattr(fix_conflict, "resolve_tier1", lambda cwd, i, d, c: True)
    monkeypatch.setattr(fix_conflict, "validate_strict_specs", lambda cwd: False)
    monkeypatch.setattr(fix_conflict, "_git", lambda cwd, *args: "")
    assert (
        fix_rebase_conflict(tmp_path, repo=REPO, item=num, default_branch="main", store=store)
        is False
    )

    # 4. Resolved and validate_strict_specs succeeds
    monkeypatch.setattr(fix_conflict, "validate_strict_specs", lambda cwd: True)
    assert (
        fix_rebase_conflict(tmp_path, repo=REPO, item=num, default_branch="main", store=store)
        is True
    )

    # 5. Not resolved
    monkeypatch.setattr(fix_conflict, "resolve_tier1", lambda cwd, i, d, c: False)
    assert (
        fix_rebase_conflict(tmp_path, repo=REPO, item=num, default_branch="main", store=store)
        is False
    )


# Tier 1 runs code of the checkout of the pull request: `uv run devops docs generate` and `uv lock`
# start the entry point of the project and its build hooks. The double of the `uv` process writes
# one of these into the clone, as such code can.
_WRITTEN = ("pre-push hook", "remote.origin.pushurl", "remote.origin.receivepack", "url.insteadOf")
_SPEC = "openspec/specs/test-cap/spec.md"


@dataclass(frozen=True)
class _Pull:
    """A bot pull request on the bare repository `upstream` whose archive commit conflicts with
    main on `_SPEC`; the clone of the step; another bare repository with the same head branch,
    whose pre-receive hook writes the token that it gets into `seen` and refuses the push; and
    `seen`, where each program of the clone writes."""

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

    def other_tip(self) -> str:
        """The tip of the head branch on the other repository, which holds the same branch."""
        return _git(self.other, "rev-parse", f"refs/heads/{self.branch}")

    def written(self) -> list[str]:
        """What the programs of the clone wrote into `seen`."""
        return sorted(path.name for path in self.seen.iterdir())


def _record(target: Path) -> str:
    """A shell line that writes the GitHub token of its environment into `target`."""
    return f"printf '%s' \"$GH_TOKEN\" > '{target}'"


def _bot(clone: Path) -> None:
    _git(clone, "config", "user.name", "Bot[bot]")
    _git(clone, "config", "user.email", "bot@example.com")


def _commit_spec(seed: Path, text: str, message: str) -> None:
    (seed / _SPEC).write_text(f"# Test Spec\n\n## Requirements\nInitial req.\n{text}", "utf-8")
    _git(seed, "add", "-A")
    _git(seed, "commit", "-q", "-m", message)


def _pull_with_archive_conflict(tmp_path: Path) -> _Pull:
    upstream = tmp_path / "upstream.git"
    other = tmp_path / "other.git"
    seen = tmp_path / "seen"
    seen.mkdir()
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(upstream))
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(other))

    seed = tmp_path / "seed"
    _git(tmp_path, "clone", "-q", str(upstream), str(seed))
    _bot(seed)
    (seed / _SPEC).parent.mkdir(parents=True)
    _commit_spec(seed, "", "chore: initial specs")
    _git(seed, "push", "-q", "origin", "main")
    store = InMemoryRoadmapStore(repo=REPO)
    number = store.seed_issue(
        title="feat: test", labels=("status/in-progress", "priority/p2-medium")
    )
    branch = f"feat/{number}-test-cap"
    _git(seed, "checkout", "-q", "-b", branch)
    change = seed / "openspec" / "changes" / f"{number}-test-cap"
    change.mkdir(parents=True)
    (change / "tasks.md").write_text("- [x] task done\n", encoding="utf-8")
    _git(seed, "add", "-A")
    _git(seed, "commit", "-q", "-m", f"feat: implement {number}")
    (change.parent / "archive").mkdir()
    shutil.move(change, change.parent / "archive" / f"2026-11-16-{number}-test-cap")
    _commit_spec(seed, f"Added req {number}.\n", f"docs(openspec): archive the change (#{number})")
    _git(seed, "push", "-q", "origin", branch)
    _git(seed, "push", "-q", str(other), branch)
    receive = other / "hooks" / "pre-receive"
    receive.write_text(f"#!/bin/sh\n{_record(seen / 'other')}\nexit 1\n", encoding="utf-8")
    receive.chmod(0o755)
    head = _git(seed, "rev-parse", "HEAD")
    _git(seed, "checkout", "-q", "main")
    _commit_spec(seed, "Main req concurrent.\n", "chore: concurrent spec update")
    _git(seed, "push", "-q", "origin", "main")

    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "-q", str(upstream), str(clone))
    _bot(clone)
    return _Pull(upstream, other, clone, seen, branch, head, number, store)


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
    monkeypatch: pytest.MonkeyPatch, pull: _Pull, written: str | None = None
) -> list[list[str]]:
    """Run the step against `pull`: GitHub gives its status, each `uv` process is the code of the
    pull request, `openspec archive` moves the change folder and `openspec validate` passes. git
    runs for real through the process runner, which gives the token to each git child that reaches
    a remote. The list holds each `uv` process."""
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
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
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
    assert "runner Job" in report.reason
    assert pull.pushed() == pull.head
    item = pull.store.item(pull.number)
    assert item is not None
    assert FixConflictRecordKey.RESULT not in item.job_record


@pytest.mark.parametrize("written", _WRITTEN)
def test_a_confirmed_round_pushes_only_to_the_url_that_it_read_after_the_clone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, written: str
) -> None:
    """With --confirm, tier 1 runs code of the pull request, and that code can write a hook or a
    git setting into the clone. The push still goes to the URL of origin that the step read after
    its clone, before that code ran, and no hook, program or other repository that the clone names
    runs."""
    pull = _pull_with_archive_conflict(tmp_path)
    ran = _with_pull_request_code(monkeypatch, pull, written)

    report = run_fix_conflict(pull.store, REPO, pull.number, source=pull.clone, confirm=True)

    assert ran
    assert pull.written() == []
    assert report.result == FixConflictResult.RESOLVED
    assert pull.pushed() == report.head != pull.head
    assert pull.other_tip() == pull.head


def test_in_a_runner_a_setting_that_tier_1_writes_stops_the_push(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, config: Callable[..., Path]
) -> None:
    """In a runner Job the step checks the git settings of the clone before each fetch and push,
    as the implement job does. A key that tier 1 wrote stops the round before the push."""
    config(roadmap={"implement": {"in_runner": True}})
    pull = _pull_with_archive_conflict(tmp_path)
    _with_pull_request_code(monkeypatch, pull, "remote.origin.pushurl")

    with pytest.raises(GitSettingsError, match=r"remote\.origin\.pushurl"):
        run_fix_conflict(pull.store, REPO, pull.number, source=pull.clone, confirm=True)

    assert pull.written() == []
    assert pull.pushed() == pull.head
    assert pull.other_tip() == pull.head


def test_a_fetch_of_the_step_reads_no_setting_of_the_clone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The step fetches at the URL that it read after the clone, in a git folder of its own, so a
    program that a setting of the clone names, such as `remote.origin.uploadpack`, never runs."""
    pull = _pull_with_archive_conflict(tmp_path)
    upload = f"{_record(pull.seen / 'uploadpack')}; git-upload-pack"
    _git(pull.clone, "config", "remote.origin.uploadpack", upload)
    _with_pull_request_code(monkeypatch, pull)

    report = run_fix_conflict(pull.store, REPO, pull.number, source=pull.clone)

    assert pull.written() == []
    assert report.result == FixConflictResult.PLANNED


def test_no_local_git_call_of_the_step_runs_a_hook_of_the_clone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each local git call of the step, such as checkout, rebase and commit, turns the hooks of the
    clone off (`core.hooksPath=/dev/null`)."""
    pull = _pull_with_archive_conflict(tmp_path)
    hooks = ("post-checkout", "pre-rebase", "post-rewrite", "pre-commit", "post-commit")
    for name in (*hooks, "prepare-commit-msg", "commit-msg"):
        hook = pull.clone / ".git" / "hooks" / name
        hook.write_text(f"#!/bin/sh\ntouch '{pull.seen / name}'\n", encoding="utf-8")
        hook.chmod(0o755)
    _with_pull_request_code(monkeypatch, pull)

    report = run_fix_conflict(pull.store, REPO, pull.number, source=pull.clone, confirm=True)

    assert pull.written() == []
    assert report.result == FixConflictResult.RESOLVED


_DOCS = "docs/CLI_REFERENCE.md"
_LOCK = "uv.lock"


def _commit_files(seed: Path, files: dict[str, str], message: str) -> None:
    for name, text in files.items():
        (seed / name).parent.mkdir(parents=True, exist_ok=True)
        (seed / name).write_text(text, encoding="utf-8")
    _git(seed, "add", "-A")
    _git(seed, "commit", "-q", "-m", message)


def _pull_with_docs_and_lock_conflict(tmp_path: Path) -> _Pull:
    """A bot pull request whose generated document and `uv.lock` conflict with main, and the clone
    of the step as `_clone_or_reuse_source` makes it: shallow, with the default branch only."""
    upstream = tmp_path / "upstream.git"
    other = tmp_path / "other.git"
    seen = tmp_path / "seen"
    seen.mkdir()
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(upstream))
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(other))
    seed = tmp_path / "seed"
    _git(tmp_path, "clone", "-q", str(upstream), str(seed))
    _bot(seed)
    _commit_files(seed, {_DOCS: "# v1\n", _LOCK: "version = 1\n"}, "chore: base")
    _git(seed, "push", "-q", "origin", "main")
    store = InMemoryRoadmapStore(repo=REPO)
    number = store.seed_issue(
        title="feat: docs", labels=("status/in-progress", "priority/p2-medium")
    )
    branch = f"feat/{number}-docs"
    _git(seed, "checkout", "-q", "-b", branch)
    changed = {_DOCS: "# v1\nbranch\n", _LOCK: "version = 1\nbranch\n", "src/feature.py": "A = 1\n"}
    _commit_files(seed, changed, "feat: a feature")
    _git(seed, "push", "-q", "origin", branch)
    head = _git(seed, "rev-parse", "HEAD")
    _git(seed, "checkout", "-q", "main")
    _commit_files(seed, {_DOCS: "# v1\nmain\n", _LOCK: "version = 1\nmain\n"}, "chore: main")
    _git(seed, "push", "-q", "origin", "main")

    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "-q", "--depth=50", upstream.as_uri(), str(clone))
    _bot(clone)
    return _Pull(upstream, other, clone, seen, branch, head, number, store)


def test_in_a_runner_a_docs_and_lockfile_round_completes_with_no_environment_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, config: Callable[..., Path]
) -> None:
    """In a runner Job, a round on a conflict of a generated document and `uv.lock` checks out the
    head branch of its shallow clone, continues the rebase with `-c core.editor=true`, generates
    both files again and pushes. No git call of the step sets an environment variable, because the
    process runner refuses an override such as `GIT_EDITOR`."""
    config(roadmap={"implement": {"in_runner": True}})
    pull = _pull_with_docs_and_lock_conflict(tmp_path)
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
    assert [cmd[1:] for cmd in ran] == [["run", "devops", "docs", "generate"], ["lock"]]
    assert pull.pushed() == report.head != pull.head
    assert git_env
    assert set(git_env) == {None}


def test_a_tier_1_round_that_cannot_generate_again_stops_the_rebase_of_the_implement_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The rebase of the implement job calls `fix_rebase_conflict`. When `devops docs generate`
    fails after tier 1 took the default branch for the conflicted document, the call returns false
    and records the stop, so the job stops the item with the class `conflict`."""
    store = InMemoryRoadmapStore(repo=REPO)
    num = store.seed_issue(title="feat: item", labels=("status/in-progress", "priority/p2-medium"))
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _bot(repo)
    _commit_files(repo, {_DOCS: "# v1\n"}, "chore: base")
    _git(repo, "checkout", "-q", "-b", "feat/branch")
    _commit_files(repo, {_DOCS: "# v1\nbranch\n", "src/feature.py": "A = 1\n"}, "feat: a feature")
    _git(repo, "checkout", "-q", "main")
    _commit_files(repo, {_DOCS: "# v1\nmain\n"}, "chore: main")
    _git(repo, "checkout", "-q", "feat/branch")
    subprocess.run([CONST_GIT_CLI, "-C", str(repo), "rebase", "main"], capture_output=True)

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
