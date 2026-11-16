"""The roadmap step `fix-conflict`: settles merge conflicts on open bot pull requests (ADR 0021,
section 8; #5019).

Runs two tiers of resolution:
1. Tier 1 (deterministic, no model): handles archive conflicts by dropping the archive commit,
   rebasing, and re-running the finish step from the change folder; handles generated docs by
   taking the base branch and running `devops docs generate`; handles `uv.lock` by taking the
   base branch and running `uv lock`.
2. Tier 2 (model): sends remaining conflicted files, both sides, and plan scope to the model.

Stops immediately if a release path (CHANGELOG.md, manifests, version lines) conflicts.
Enforces safety bounds: bot pull requests only, no human commits after bot push, no human claims
or owner/* labels, soft cap 2 rounds (extendable to 3 if conflicted files decrease), hard cap 4.
Runs `openspec validate --specs --strict` and scoped checks before pushing.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Final

from devops_cli.config.commands import BIN_DEVOPS, BIN_OPENSPEC, BIN_UV
from devops_cli.config.constants import (
    CONST_CHANGELOG_FILENAME,
    CONST_GIT_CLI,
    CONST_GIT_MAIN_BRANCH,
    CONST_GIT_REMOTE_ORIGIN,
)
from devops_cli.config.settings import RoadmapFixConflictConfig, load_settings
from devops_cli.core.process import run_subprocess
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.exceptions import GitOperationError
from devops_cli.git.branch_form import parse_branch
from devops_cli.github.client import PullStatus
from devops_cli.github.session import get_github_session
from devops_cli.roadmap.claim import claim_labels, claimed_by
from devops_cli.roadmap.implement.implement_step import find_change
from devops_cli.roadmap.stores.store import (
    FixConflictRecordKey,
    Item,
    RoadmapStore,
)

logger = logging.getLogger(__name__)

_GIT_OPERATION: Final[str] = "roadmap fix-conflict"
_BOT_SUFFIX: Final[str] = "[bot]"
_RELEASE_PATHS: Final[frozenset[str]] = frozenset(
    {
        CONST_CHANGELOG_FILENAME,
        ".release-please-manifest.json",
        "release-please-config.json",
    }
)
_GENERATED_DOC_PATHS: Final[frozenset[str]] = frozenset(
    {
        "docs/CLI_REFERENCE.md",
        "docs/CONFIGURATION.md",
        "docs/ENV_VARS.md",
        "docs/ERRORS.md",
        "docs/KNOWLEDGE_BASE.md",
        "docs/MCP_TOOLS.md",
        "docs/TELEMETRY.md",
        "CLAUDE.md",
        "GEMINI.md",
        ".github/copilot-instructions.md",
    }
)


class FixConflictResult(StrEnum):
    """The result of the fix-conflict step (#5019)."""

    RESOLVED = "resolved"
    NO_CONFLICT = "no_conflict"
    REFUSED = "refused"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass(frozen=True)
class FixConflictReport:
    """The outcome of the fix-conflict step for a pull request."""

    repo: str
    pull: int
    result: FixConflictResult
    head: str = ""
    rounds: int = 0
    files: tuple[str, ...] = ()
    reason: str = ""

    def to_json(self) -> str:
        data: dict[str, Any] = {
            "job": "fix_conflict",
            "repo": self.repo,
            "pull": self.pull,
            "result": self.result.value,
        }
        if self.head:
            data["head"] = self.head
        if self.rounds:
            data["rounds"] = self.rounds
        if self.files:
            data["files"] = list(self.files)
        if self.reason:
            data["reason"] = self.reason
        return json.dumps(data)


def _git(cwd: Path, *args: str) -> str:
    proc = run_subprocess([CONST_GIT_CLI, "-C", str(cwd), *args], check=False, quiet=True)
    if proc.returncode != 0:
        raise GitOperationError(
            f"git {' '.join(args)} failed: {proc.stderr.strip() or proc.stdout.strip()}",
            operation=_GIT_OPERATION,
        )
    return proc.stdout.strip()


def _abort_rebase(cwd: Path) -> None:
    proc = run_subprocess(
        [CONST_GIT_CLI, "-C", str(cwd), "rebase", "--abort"], check=False, quiet=True
    )
    if proc.returncode != 0:
        logger.debug("rebase --abort returned %d: %s", proc.returncode, proc.stderr)


def is_release_path(path: str, diff_text: str = "") -> bool:
    """Whether a path or diff hunk modifies release metadata or manifests (#5019)."""
    if path in _RELEASE_PATHS or path.startswith(".release-please"):
        return True
    if diff_text:
        if re.search(r"^[+-]\s*version\s*=\s*", diff_text, re.MULTILINE):
            return True
        if re.search(r"^[+-]\s*__version__\s*=\s*", diff_text, re.MULTILINE):
            return True
    return False


def is_archive_path(path: str) -> bool:
    """Whether a path belongs to OpenSpec archive or specs (#5019)."""
    return path.startswith("openspec/specs/") or path.startswith("openspec/changes/archive/")


def is_generated_docs_path(path: str) -> bool:
    """Whether a path is a generated documentation reference (#5019)."""
    return path in _GENERATED_DOC_PATHS or path.startswith("docs/commands/")


def is_lockfile_path(path: str) -> bool:
    """Whether a path is a lockfile (#5019)."""
    return path == "uv.lock"


def check_merge_tree_conflict(cwd: Path, base_ref: str, head_ref: str) -> tuple[bool, list[str]]:
    """Check whether merging head_ref into base_ref causes merge conflicts (#5019)."""
    proc = run_subprocess(
        [CONST_GIT_CLI, "-C", str(cwd), "merge-tree", "--write-tree", base_ref, head_ref],
        check=False,
        quiet=True,
    )
    if proc.returncode == 0:
        return False, []
    conflicted: list[str] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if "CONFLICT (content): Merge conflict in " in line:
            conflicted.append(line.split("CONFLICT (content): Merge conflict in ", 1)[1])
        elif "CONFLICT" in line and " in " in line:
            conflicted.append(line.rsplit(" in ", 1)[1])
    return True, sorted(set(conflicted))


def conflicted_files(cwd: Path) -> list[str]:
    """The unmerged paths in a repository during a rebase or merge (#5019)."""
    proc = run_subprocess(
        [CONST_GIT_CLI, "-C", str(cwd), "diff", "--name-only", "--diff-filter=U", "-z"],
        check=False,
        quiet=True,
    )
    if proc.returncode != 0:
        return []
    out = proc.stdout.strip()
    if not out:
        return []
    return [p for p in out.split("\0") if p]


def _is_bot_author(author: str) -> bool:
    if not author:
        return False
    if author.endswith(_BOT_SUFFIX):
        return True
    bot = load_settings().service.github_app.bot_login
    return bool(bot and author == bot)


def _check_admission_bounds(
    status: PullStatus,
    item: Item | None,
    expected_head: str | None = None,
) -> str | None:
    """Validate safety bounds before attempting conflict settlement (#5019)."""
    if expected_head and status.head_sha != expected_head:
        return (
            f"PR #{status.head_ref} head moved: expected {expected_head}, found {status.head_sha}"
        )

    if not _is_bot_author(status.author):
        return f"PR author {status.author} is not a bot"

    # Stop on an owner/* label but the Service's own claim (#5027)
    for label in claim_labels(status.labels):
        return f"PR holds owner label: {label}"

    if item is not None:
        for label in claim_labels(item.labels):
            return f"Item #{item.number} holds owner label: {label}"
        owner = claimed_by(item)
        if owner is not None:
            return f"Item #{item.number} is claimed by {owner}"

    return None


def _check_no_human_commit_after_bot(cwd: Path, base_ref: str, head_ref: str) -> bool:
    """Ensure no human committed past the last bot commit (#5019)."""
    log_output = _git(cwd, "log", "--format=%an|%ae", f"{base_ref}..{head_ref}")
    if not log_output:
        return True
    lines = [line.strip() for line in log_output.splitlines() if line.strip()]
    for author_line in lines:
        name, _, email = author_line.partition("|")
        is_bot = (
            _is_bot_author(name)
            or _BOT_SUFFIX in name
            or (email and "github-actions" in email)
            or (email and _BOT_SUFFIX in email)
        )
        if not is_bot:
            return False
    return True


def _find_archive_commit(cwd: Path, base_ref: str) -> str | None:
    """Find the commit on the branch that created or modified openspec archive (#5019)."""
    proc = run_subprocess(
        [CONST_GIT_CLI, "-C", str(cwd), "rev-list", f"{base_ref}..HEAD"],
        check=False,
        quiet=True,
    )
    if proc.returncode != 0:
        return None
    commits = proc.stdout.splitlines()
    for sha in commits:
        sha = sha.strip()
        if not sha:
            continue
        msg = _git(cwd, "log", "-1", "--format=%s", sha)
        if "archive the change" in msg:
            return sha
        files = _git(cwd, "diff-tree", "--no-commit-id", "--name-only", "-r", sha)
        if any(f.startswith("openspec/changes/archive/") for f in files.splitlines()):
            return sha
    return None


def _resolve_tier1_archive(cwd: Path, item_number: int, base_ref: str) -> bool:
    logger.info(
        "All conflicts are OpenSpec archive paths; dropping archive commit and re-running finish"
    )
    _abort_rebase(cwd)
    archive_sha = _find_archive_commit(cwd, base_ref)
    if not archive_sha:
        logger.warning("Could not find archive commit to drop")
        return False

    # Drop the archive commit
    head_sha = _git(cwd, "rev-parse", "HEAD")
    if head_sha == archive_sha:
        _git(cwd, "reset", "--hard", "HEAD~1")
    else:
        _git(cwd, "rebase", "--onto", f"{archive_sha}^", archive_sha, "HEAD")

    # Rebase non-archive commits onto base_ref
    try:
        _git(cwd, "rebase", base_ref)
    except GitOperationError:
        _abort_rebase(cwd)
        return False

    # Find active change folder
    try:
        active_change = find_change(cwd, item_number, archived=False)
    except FileNotFoundError, ValueError:
        active_change = None

    if active_change is None or not active_change.exists():
        logger.warning("No active change folder found after dropping archive commit")
        return False

    # Regenerate docs and re-archive change
    docs_proc = run_subprocess(
        [BIN_UV, "run", BIN_DEVOPS, "docs", "generate"], cwd=cwd, check=False, quiet=True
    )
    if docs_proc.returncode != 0:
        logger.warning("docs generate failed: %s", docs_proc.stderr)
        return False

    archive_proc = run_subprocess(
        [BIN_OPENSPEC, "archive", active_change.name, "--yes"],
        cwd=cwd,
        check=False,
        quiet=True,
    )
    if archive_proc.returncode != 0:
        logger.warning("openspec archive failed: %s", archive_proc.stderr)
        return False

    _git(cwd, "add", "-A")
    status = _git(cwd, "status", "--porcelain")
    if status:
        _git(cwd, "commit", "-m", f"docs(openspec): archive the change (#{item_number})")
    return True


def _regenerate_docs_and_commit(cwd: Path, item_number: int) -> bool:
    docs_proc = run_subprocess(
        [BIN_UV, "run", BIN_DEVOPS, "docs", "generate"], cwd=cwd, check=False, quiet=True
    )
    if docs_proc.returncode != 0:
        logger.warning("docs generate failed: %s", docs_proc.stderr)
        return False
    _git(cwd, "add", "-A")
    if _git(cwd, "status", "--porcelain"):
        _git(cwd, "commit", "-m", f"docs: regenerate the documentation (#{item_number})")
    return True


def _regenerate_lock_and_commit(cwd: Path, item_number: int) -> bool:
    lock_proc = run_subprocess([BIN_UV, "lock"], cwd=cwd, check=False, quiet=True)
    if lock_proc.returncode != 0:
        logger.warning("uv lock failed: %s", lock_proc.stderr)
        return False
    _git(cwd, "add", "uv.lock")
    if _git(cwd, "status", "--porcelain"):
        _git(cwd, "commit", "-m", f"chore(deps): update lockfile (#{item_number})")
    return True


def _resolve_tier1_docs_lockfile(
    cwd: Path,
    item_number: int,
    base_ref: str,
    conflicts: Sequence[str],
) -> bool:
    logger.info("Conflicts are generated docs and/or lockfile; resolving from %s", base_ref)
    regenerate_docs = False
    regenerate_lock = False
    for c in conflicts:
        _git(cwd, "checkout", "--ours", c)
        _git(cwd, "add", c)
        if is_generated_docs_path(c):
            regenerate_docs = True
        if is_lockfile_path(c):
            regenerate_lock = True

    proc = run_subprocess(
        [CONST_GIT_CLI, "-C", str(cwd), "rebase", "--continue"],
        check=False,
        quiet=True,
        env=dict(os.environ, GIT_EDITOR="true"),
    )
    if proc.returncode != 0:
        _abort_rebase(cwd)
        return False

    if regenerate_docs and not _regenerate_docs_and_commit(cwd, item_number):
        return False

    if regenerate_lock and not _regenerate_lock_and_commit(cwd, item_number):
        return False

    return True


def _has_release_path_conflict(cwd: Path, conflicts: Sequence[str]) -> bool:
    for c in conflicts:
        proc = run_subprocess([CONST_GIT_CLI, "-C", str(cwd), "diff", c], check=False, quiet=True)
        diff_text = proc.stdout if proc.returncode == 0 else ""
        if is_release_path(c, diff_text):
            return True
    return False


def resolve_tier1(
    cwd: Path,
    item_number: int,
    default_branch: str,
    conflicts: Sequence[str],
) -> bool:
    """Resolve deterministic conflicts (archive, generated docs, lockfile) without model calls (#5019)."""
    if _has_release_path_conflict(cwd, conflicts):
        logger.info("Conflict on release path stops Tier 1")
        return False

    base_ref = f"origin/{default_branch}"

    if all(is_archive_path(c) for c in conflicts):
        return _resolve_tier1_archive(cwd, item_number, base_ref)

    if all(is_generated_docs_path(c) or is_lockfile_path(c) for c in conflicts):
        return _resolve_tier1_docs_lockfile(cwd, item_number, base_ref, conflicts)

    return False


def validate_strict_specs(cwd: Path) -> bool:
    """Run `openspec validate --specs --strict` before push (#5019)."""
    proc = run_subprocess(
        [BIN_OPENSPEC, "validate", "--specs", "--strict"],
        cwd=cwd,
        check=False,
        quiet=True,
    )
    return proc.returncode == 0


def _record_fix_conflict_marks(
    store: RoadmapStore | None,
    item: int | Item | None,
    *,
    key: str | None = None,
    rounds: int,
    files: Sequence[str],
    result: FixConflictResult,
) -> None:
    if store is None or item is None:
        return
    item_obj = store.item(item) if isinstance(item, int) else item
    if item_obj is None:
        return
    marks: dict[str, str] = {
        FixConflictRecordKey.ROUNDS: str(rounds),
        FixConflictRecordKey.FILES: json.dumps(list(files)),
        FixConflictRecordKey.RESULT: result.value,
    }
    if key:
        marks[FixConflictRecordKey.KEY] = key
    store.set_marks(item_obj, marks)


def fix_rebase_conflict(
    cwd: Path,
    *,
    repo: str,
    item: int,
    default_branch: str,
    store: RoadmapStore | None = None,
) -> bool:
    """Programmatic helper for implement runner Job on rebase conflict (#5019).

    Attempts Tier 1 deterministic settlement. Returns True if resolved cleanly,
    or False if conflict requires human/model intervention.
    """
    conflicts = conflicted_files(cwd)
    if not conflicts:
        return False

    if _has_release_path_conflict(cwd, conflicts):
        _abort_rebase(cwd)
        _record_fix_conflict_marks(
            store, item, rounds=1, files=conflicts, result=FixConflictResult.STOPPED
        )
        return False

    resolved = resolve_tier1(cwd, item, default_branch, conflicts)
    if resolved:
        if not validate_strict_specs(cwd):
            logger.warning("Strict spec validation failed after Tier 1 conflict resolution")
            _git(cwd, "reset", "--hard", f"origin/{default_branch}")
            return False

        _record_fix_conflict_marks(
            store, item, rounds=1, files=[], result=FixConflictResult.RESOLVED
        )
        return True

    _abort_rebase(cwd)
    _record_fix_conflict_marks(
        store, item, rounds=1, files=conflicts, result=FixConflictResult.STOPPED
    )
    return False


def _read_item_conflict_state(item: Item | None) -> tuple[int, list[str]]:
    if item is None:
        return 0, []
    record = item.job_record
    rounds = int(record.get(FixConflictRecordKey.ROUNDS) or "0")
    try:
        files = json.loads(record.get(FixConflictRecordKey.FILES) or "[]")
    except json.JSONDecodeError, TypeError, ValueError:
        files = []
    return rounds, files


def _clone_or_reuse_source(repo: str, source: Path | None) -> tuple[Path, Path | None]:
    if source is not None:
        return source, None
    temp_dir = Path(tempfile.mkdtemp(prefix="fix-conflict-"))
    worktree = temp_dir / "repo"
    proc = run_subprocess(
        [CONST_GIT_CLI, "clone", "--depth=50", f"https://github.com/{repo}.git", str(worktree)],
        check=False,
        quiet=True,
    )
    if proc.returncode != 0:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise GitOperationError(
            f"Failed to clone repository: {proc.stderr}", operation=_GIT_OPERATION
        )
    return worktree, temp_dir


def _check_conflict_caps(
    current_rounds: int,
    conflicts: Sequence[str],
    prev_files: Sequence[str],
    settings: RoadmapFixConflictConfig,
) -> str | None:
    if current_rounds >= settings.hard_cap_rounds:
        return f"Hard cap reached ({settings.hard_cap_rounds} rounds)"
    if current_rounds >= settings.soft_cap_rounds:
        if not (prev_files and len(conflicts) < len(prev_files)):
            return (
                f"Soft cap reached ({settings.soft_cap_rounds} rounds) without conflict reduction"
            )
    return None


def _attempt_rebase_and_tier1(
    worktree: Path,
    item_num: int,
    default_branch: str,
    base_ref: str,
    settings: RoadmapFixConflictConfig,
) -> tuple[bool, list[str]]:
    rebase_proc = run_subprocess(
        [CONST_GIT_CLI, "-C", str(worktree), "rebase", base_ref],
        check=False,
        quiet=True,
    )
    conflicts = conflicted_files(worktree)
    if rebase_proc.returncode == 0 or not conflicts:
        return True, []
    if settings.tier1_mode == "on":
        resolved = resolve_tier1(worktree, item_num, default_branch, conflicts)
        if resolved:
            return True, []
    return False, conflicts


def _settle_rebase_conflict(
    worktree: Path,
    *,
    store: RoadmapStore,
    item: Item | None,
    item_num: int | None,
    repo: str,
    pull: int,
    status: PullStatus,
    settings: RoadmapFixConflictConfig,
    base_ref: str,
    default_branch: str,
    current_rounds: int,
    confirm: bool,
) -> FixConflictReport:
    resolved, conflicts = _attempt_rebase_and_tier1(
        worktree,
        item_num or pull,
        default_branch,
        base_ref,
        settings,
    )

    if not resolved:
        _abort_rebase(worktree)
        new_rounds = current_rounds + 1
        _record_fix_conflict_marks(
            store,
            item,
            key=f"{_git(worktree, 'rev-parse', base_ref)}:{status.head_sha}",
            rounds=new_rounds,
            files=conflicts,
            result=FixConflictResult.STOPPED,
        )
        return FixConflictReport(
            repo=repo,
            pull=pull,
            result=FixConflictResult.STOPPED,
            head=status.head_sha,
            rounds=new_rounds,
            files=tuple(conflicts),
            reason="Tier 2 is in plan mode without --confirm"
            if settings.tier2_mode == "plan" and not confirm
            else "Conflict could not be resolved by Tier 1",
        )

    if not validate_strict_specs(worktree):
        _abort_rebase(worktree)
        _git(worktree, "reset", "--hard", status.head_sha)
        return FixConflictReport(
            repo=repo,
            pull=pull,
            result=FixConflictResult.FAILED,
            head=status.head_sha,
            rounds=current_rounds + 1,
            reason="openspec validate --specs --strict failed",
        )

    new_head = _git(worktree, "rev-parse", "HEAD")
    _git(worktree, "push", "--force-with-lease", CONST_GIT_REMOTE_ORIGIN, f"HEAD:{status.head_ref}")

    new_rounds = current_rounds + 1
    _record_fix_conflict_marks(
        store,
        item,
        key=f"{_git(worktree, 'rev-parse', base_ref)}:{new_head}",
        rounds=new_rounds,
        files=[],
        result=FixConflictResult.RESOLVED,
    )

    return FixConflictReport(
        repo=repo,
        pull=pull,
        result=FixConflictResult.RESOLVED,
        head=new_head,
        rounds=new_rounds,
        files=(),
    )


def _execute_fix_conflict_in_worktree(
    worktree: Path,
    *,
    store: RoadmapStore,
    item: Item | None,
    item_num: int | None,
    repo: str,
    pull: int,
    status: PullStatus,
    settings: RoadmapFixConflictConfig,
    default_branch: str,
    current_rounds: int,
    prev_files: list[str],
    confirm: bool,
) -> FixConflictReport:
    _git(worktree, "fetch", CONST_GIT_REMOTE_ORIGIN, status.head_ref)
    _git(worktree, "fetch", CONST_GIT_REMOTE_ORIGIN, default_branch)
    _git(worktree, "checkout", status.head_ref)

    base_ref = f"{CONST_GIT_REMOTE_ORIGIN}/{default_branch}"
    head_ref = f"{CONST_GIT_REMOTE_ORIGIN}/{status.head_ref}"

    if not _check_no_human_commit_after_bot(worktree, base_ref, head_ref):
        return FixConflictReport(
            repo=repo,
            pull=pull,
            result=FixConflictResult.REFUSED,
            head=status.head_sha,
            reason="Human commit detected after bot push",
        )

    has_conflict, initial_conflicts = check_merge_tree_conflict(worktree, base_ref, head_ref)
    if not has_conflict:
        return FixConflictReport(
            repo=repo,
            pull=pull,
            result=FixConflictResult.NO_CONFLICT,
            head=status.head_sha,
            rounds=current_rounds,
            reason="No merge conflict detected",
        )

    cap_error = _check_conflict_caps(current_rounds, initial_conflicts, prev_files, settings)
    if cap_error:
        return FixConflictReport(
            repo=repo,
            pull=pull,
            result=FixConflictResult.STOPPED,
            head=status.head_sha,
            rounds=current_rounds,
            files=tuple(initial_conflicts),
            reason=cap_error,
        )

    return _settle_rebase_conflict(
        worktree,
        store=store,
        item=item,
        item_num=item_num,
        repo=repo,
        pull=pull,
        status=status,
        settings=settings,
        base_ref=base_ref,
        default_branch=default_branch,
        current_rounds=current_rounds,
        confirm=confirm,
    )


def run_fix_conflict(
    store: RoadmapStore,
    repo: str,
    pull: int,
    *,
    head: str | None = None,
    confirm: bool = False,
    source: Path | None = None,
) -> FixConflictReport:
    """Execute the fix-conflict step on pull request `pull` (#5019)."""
    client = get_github_session().client
    status = client.get_pull_status(repo, pull)

    item_num = None
    parts = parse_branch(status.head_ref)
    if parts:
        item_num = parts.issue

    item = store.item(item_num) if item_num else None

    # Safety bounds check
    admission_error = _check_admission_bounds(status, item, expected_head=head)
    if admission_error:
        logger.info("fix-conflict refused PR #%d: %s", pull, admission_error)
        return FixConflictReport(
            repo=repo,
            pull=pull,
            result=FixConflictResult.REFUSED,
            head=status.head_sha,
            reason=admission_error,
        )

    settings = load_settings().roadmap.fix_conflict
    current_rounds, prev_files = _read_item_conflict_state(item)

    if current_rounds >= settings.hard_cap_rounds:
        return FixConflictReport(
            repo=repo,
            pull=pull,
            result=FixConflictResult.STOPPED,
            head=status.head_sha,
            rounds=current_rounds,
            reason=f"Hard cap reached ({settings.hard_cap_rounds} rounds)",
        )

    default_branch = status.default_branch or CONST_GIT_MAIN_BRANCH
    try:
        worktree, temp_dir = _clone_or_reuse_source(repo, source)
    except GitOperationError as exc:
        return FixConflictReport(
            repo=repo,
            pull=pull,
            result=FixConflictResult.FAILED,
            head=status.head_sha,
            reason=str(exc),
        )

    try:
        return _execute_fix_conflict_in_worktree(
            worktree,
            store=store,
            item=item,
            item_num=item_num,
            repo=repo,
            pull=pull,
            status=status,
            settings=settings,
            default_branch=default_branch,
            current_rounds=current_rounds,
            prev_files=prev_files,
            confirm=confirm,
        )
    finally:
        if temp_dir is not None:
            shutil.rmtree(temp_dir, ignore_errors=True)


def dry_run_fix_conflict(
    repo: str, pull: int
) -> tuple[tuple[PlannedRequest, ...], tuple[PlannedRequest, ...]]:
    """Dry-run planned requests for fix-conflict (ADR 0021; #5019). Sees 0 requests."""
    return (), ()
