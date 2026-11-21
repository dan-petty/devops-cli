"""The roadmap step `fix-conflict`: settles merge conflicts on open bot pull requests (ADR 0021,
section 8; #5019).

Runs two tiers of resolution:
1. Tier 1 (deterministic, no model): handles archive conflicts by dropping the archive commit,
   rebasing, and re-running the finish step from the change folder; handles generated docs by
   taking the base branch and running `devops docs generate`; handles `uv.lock` by taking the
   base branch and running `uv lock`.
2. Tier 2 (model) is not built: a conflict that tier 1 does not settle stops the round.

Tier 1 runs code of the checkout of the pull request: `devops docs generate` and `uv lock` start
the project and its build hooks. So `run_fix_conflict` rebases and resolves only with `confirm`,
which the command gives only in a runner Job (`require_runner`), after the Job makes its process
unreadable and adopts the orphans of that code, as fix-checks does. Without `confirm`, as on a
workstation, the step finds the conflict and returns `planned`: it runs no code of the checkout,
pushes nothing and writes no record.

The step reads the URL of `origin` right after its clone, before any other git call. Each fetch
and each push runs through `OriginGit` at that URL, in a git folder of its own that reads no
setting, hook or credential helper of the clone. Each local git call turns the hooks of the clone
off (`CONST_GIT_HOOKS_OFF_CONFIG`). The clone commits as the bot (`commit_author`), as the clone of
`ensure_checkout` does. The clone is shallow, so the step deepens it through `OriginGit` until it
holds the merge base of the head branch and the default branch. Only a rebase that ends, or whose
conflicts tier 1 settles, gives a result, and the step pushes it only when it is the head branch,
holds the default branch and differs from its tip, and holds each change of the pull request.

Stops immediately if a release path (CHANGELOG.md, manifests, version lines) conflicts.
Enforces safety bounds: bot pull requests only, no human commits after bot push, no human claims
or owner/* labels, soft cap 2 rounds (extendable to 3 if conflicted files decrease), hard cap 4.
Runs `openspec validate --specs --strict` and scoped checks before pushing.
"""

from __future__ import annotations

import json
import logging
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
    CONST_GIT_HOOKS_OFF_CONFIG,
    CONST_GIT_MAIN_BRANCH,
    CONST_GIT_NO_EDITOR_CONFIG,
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
from devops_cli.roadmap.implement.git_isolation import OriginGit, origin_url
from devops_cli.roadmap.implement.implement_step import find_change
from devops_cli.roadmap.run import commit_author
from devops_cli.roadmap.stores.store import (
    FixConflictRecordKey,
    Item,
    RoadmapStore,
)
from devops_cli.security.sanitizer import mask_secrets

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
_RUNNER_NOTE: Final[str] = (
    "Tier 1 runs code of the pull request (`devops docs generate`, `uv lock`), so it runs only "
    "with --confirm in a runner Job."
)
# The commits that the first deepening of the shallow clone adds; each next one adds twice as many.
_DEEPEN_FIRST: Final[int] = 50
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
    PLANNED = "planned"
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


def _git_argv(cwd: Path, *args: str) -> list[str]:
    """`git -C <cwd> <args>` with the hooks of the clone off: the step runs none of them."""
    return [CONST_GIT_CLI, "-C", str(cwd), "-c", CONST_GIT_HOOKS_OFF_CONFIG, *args]


def _git(cwd: Path, *args: str) -> str:
    proc = run_subprocess(_git_argv(cwd, *args), check=False, quiet=True)
    if proc.returncode != 0:
        raise GitOperationError(
            f"git {' '.join(args)} failed: {proc.stderr.strip() or proc.stdout.strip()}",
            operation=_GIT_OPERATION,
        )
    return proc.stdout.strip()


def _abort_rebase(cwd: Path) -> None:
    proc = run_subprocess(_git_argv(cwd, "rebase", "--abort"), check=False, quiet=True)
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
        _git_argv(cwd, "merge-tree", "--write-tree", base_ref, head_ref),
        check=False,
        quiet=True,
    )
    if proc.returncode == 0:
        return False, []
    if proc.returncode != 1:
        raise GitOperationError(
            f"git merge-tree failed: {proc.stderr.strip() or proc.stdout.strip()}",
            operation=_GIT_OPERATION,
        )
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
        _git_argv(cwd, "diff", "--name-only", "--diff-filter=U", "-z"),
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
        _git_argv(cwd, "rev-list", f"{base_ref}..HEAD"),
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
        _git(cwd, "checkout", "--ours", "--", c)
        _git(cwd, "add", "--", c)
        if is_generated_docs_path(c):
            regenerate_docs = True
        if is_lockfile_path(c):
            regenerate_lock = True

    proc = run_subprocess(
        _git_argv(cwd, "-c", CONST_GIT_NO_EDITOR_CONFIG, "rebase", "--continue"),
        check=False,
        quiet=True,
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
        proc = run_subprocess(_git_argv(cwd, "diff", "--", c), check=False, quiet=True)
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
        [
            CONST_GIT_CLI,
            "-c",
            CONST_GIT_HOOKS_OFF_CONFIG,
            "clone",
            "--depth=50",
            f"https://github.com/{repo}.git",
            str(worktree),
        ],
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
) -> tuple[bool, list[str], str]:
    """Rebase the head branch onto `base_ref` and settle its conflicts with tier 1: whether the
    rebase ended, the conflicted paths, and the reason of a stop. A rebase that fails with no
    unmerged path failed for another cause, such as a commit that git refuses, and tier 1 settles
    nothing there."""
    rebase_proc = run_subprocess(
        _git_argv(worktree, "rebase", base_ref),
        check=False,
        quiet=True,
    )
    if rebase_proc.returncode == 0:
        return True, [], ""
    conflicts = conflicted_files(worktree)
    if not conflicts:
        lines = (rebase_proc.stderr.strip() or rebase_proc.stdout.strip()).splitlines()
        cause = mask_secrets(lines[-1]) if lines else f"exit {rebase_proc.returncode}"
        return False, [], f"The rebase failed with no conflicted file: {cause}"
    if settings.tier1_mode == "on" and resolve_tier1(worktree, item_num, default_branch, conflicts):
        return True, [], ""
    return False, conflicts, "Conflict could not be resolved by Tier 1"


def _names(cwd: Path, old: str, new: str) -> set[str]:
    """The paths that differ between the commits `old` and `new`, a rename as two paths."""
    listed = _git(cwd, "diff", "--name-only", "--no-renames", "-z", old, new, "--")
    return {name for name in listed.split("\0") if name}


def _push_refused(cwd: Path, base_ref: str, head_ref: str, branch: str) -> str | None:
    """Why HEAD is no result to push to `branch`, or None. HEAD must be the branch, so no rebase
    stopped on the way. It must hold the tip of `base_ref` and differ from it, and hold the version
    of `head_ref` of each path that the pull request changed, but a path that `base_ref` also
    changed or that tier 1 generates. So the step never pushes the tip of the default branch."""
    on = run_subprocess(_git_argv(cwd, "symbolic-ref", "-q", "HEAD"), check=False, quiet=True)
    if on.stdout.strip() != f"refs/heads/{branch}":
        return f"HEAD is not the branch {branch}."
    if _git(cwd, "rev-parse", "HEAD") == _git(cwd, "rev-parse", base_ref):
        return f"The result is the tip of {base_ref}."
    holds = run_subprocess(
        _git_argv(cwd, "merge-base", "--is-ancestor", base_ref, "HEAD"), check=False, quiet=True
    )
    if holds.returncode != 0:
        return f"The result does not hold {base_ref}."
    fork = _git(cwd, "merge-base", base_ref, head_ref)
    changed = _names(cwd, fork, head_ref) - _names(cwd, fork, base_ref)
    kept = {
        path
        for path in changed
        if not (is_archive_path(path) or is_generated_docs_path(path) or is_lockfile_path(path))
    }
    lacking = sorted(kept & _names(cwd, head_ref, "HEAD"))
    if lacking:
        return f"The result lacks the change of the pull request: {', '.join(lacking)}"
    return None


def _merge_base(cwd: Path, base_ref: str, head_ref: str) -> str | None:
    proc = run_subprocess(_git_argv(cwd, "merge-base", base_ref, head_ref), check=False, quiet=True)
    return proc.stdout.strip() if proc.returncode == 0 else None


def _fetch_to_merge_base(cwd: Path, origin: OriginGit, head: str, default: str) -> str | None:
    """Fetch the head branch and the default branch through `origin`, and give their merge base.
    A shallow clone, as the clone of the step is, deepens through `origin`, twice as far each time,
    until it holds the merge base or the whole history, or a deepening adds no commit. None when
    the history holds no merge base then."""
    base_ref = f"{CONST_GIT_REMOTE_ORIGIN}/{default}"
    head_ref = f"{CONST_GIT_REMOTE_ORIGIN}/{head}"
    origin.fetch(head, default)
    found = _merge_base(cwd, base_ref, head_ref)
    deepen = _DEEPEN_FIRST
    while found is None and _git(cwd, "rev-parse", "--is-shallow-repository") == "true":
        held = _git(cwd, "rev-list", "--count", base_ref, head_ref)
        origin.fetch(head, default, deepen=deepen)
        found = _merge_base(cwd, base_ref, head_ref)
        if _git(cwd, "rev-list", "--count", base_ref, head_ref) == held:
            break
        deepen *= 2
    return found


def _plan_reason(conflicts: Sequence[str], tier1_mode: str) -> str:
    """What a confirmed round would do with the conflicted paths `conflicts`, by the rules of
    `resolve_tier1`. A release path that only the diff of the rebase shows, such as a version
    line, stops the round but not the plan."""
    if tier1_mode != "on":
        action = "stop, because roadmap.fix_conflict.tier1_mode is not on"
    elif any(is_release_path(path) for path in conflicts):
        action = "stop on the release path"
    elif all(is_archive_path(path) for path in conflicts):
        action = "drop the archive commit, rebase and archive the change again with tier 1"
    elif all(is_generated_docs_path(path) or is_lockfile_path(path) for path in conflicts):
        action = "take the default branch for these files and generate them again with tier 1"
    else:
        action = (
            "stop, because tier 1 settles only archive, generated document and lockfile conflicts"
        )
    return f"Plan: {action}. {_RUNNER_NOTE}"


def _settle_rebase_conflict(
    worktree: Path,
    *,
    origin: OriginGit,
    store: RoadmapStore,
    item: Item | None,
    item_num: int | None,
    repo: str,
    pull: int,
    status: PullStatus,
    settings: RoadmapFixConflictConfig,
    base_ref: str,
    head_ref: str,
    default_branch: str,
    current_rounds: int,
) -> FixConflictReport:
    resolved, conflicts, reason = _attempt_rebase_and_tier1(
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
            reason=reason,
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

    refused = _push_refused(worktree, base_ref, head_ref, status.head_ref)
    if refused is not None:
        return FixConflictReport(
            repo=repo,
            pull=pull,
            result=FixConflictResult.FAILED,
            head=status.head_sha,
            rounds=current_rounds + 1,
            reason=refused,
        )

    new_head = _git(worktree, "rev-parse", "HEAD")
    origin.push(status.head_ref, new_head, lease=status.head_sha)

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
    origin: OriginGit,
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
    base_ref = f"{CONST_GIT_REMOTE_ORIGIN}/{default_branch}"
    head_ref = f"{CONST_GIT_REMOTE_ORIGIN}/{status.head_ref}"
    if _fetch_to_merge_base(worktree, origin, status.head_ref, default_branch) is None:
        return FixConflictReport(
            repo=repo,
            pull=pull,
            result=FixConflictResult.FAILED,
            head=status.head_sha,
            reason=f"The history holds no merge base of {base_ref} and {head_ref}.",
        )

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

    if not confirm:
        return FixConflictReport(
            repo=repo,
            pull=pull,
            result=FixConflictResult.PLANNED,
            head=status.head_sha,
            rounds=current_rounds,
            files=tuple(initial_conflicts),
            reason=_plan_reason(initial_conflicts, settings.tier1_mode),
        )

    _git(worktree, "checkout", "-B", status.head_ref, head_ref)
    return _settle_rebase_conflict(
        worktree,
        origin=origin,
        store=store,
        item=item,
        item_num=item_num,
        repo=repo,
        pull=pull,
        status=status,
        settings=settings,
        base_ref=base_ref,
        head_ref=head_ref,
        default_branch=default_branch,
        current_rounds=current_rounds,
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
    """Execute the fix-conflict step on pull request `pull` (#5019). Without `confirm` the step
    returns its plan, runs no code of the checkout and writes nothing. With `confirm` it rebases,
    runs tier 1, which runs code of the pull request, and pushes: only a runner Job passes it, after
    `require_runner` and the hardening of its process, as the command does."""
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
        # The URL of `origin`, read right after the clone, before any code of the pull request runs.
        origin = OriginGit(worktree, origin_url(worktree))
        # The clone commits as the bot, as the clone of `ensure_checkout` does.
        name, email = commit_author()
        _git(worktree, "config", "user.name", name)
        _git(worktree, "config", "user.email", email)
        return _execute_fix_conflict_in_worktree(
            worktree,
            origin=origin,
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
