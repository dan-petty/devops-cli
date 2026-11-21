"""The roadmap step `fix-conflict`: settles merge conflicts on open bot pull requests (ADR 0021,
section 8; #5019).

Tier 1 (deterministic, no model) settles each stop of the rebase onto the default branch. It takes
the side of the default branch for generated documents and `uv.lock` (`git checkout --ours`, or
`git rm` for a file that the default branch deleted), and runs `devops docs generate` and `uv lock`
after the rebase. It drops only the archive commit of the item, which moves its change folder into
the archive (`git rebase --skip`), and archives the change again after the rebase, in a commit of
its own. Tier 2 (model) is not built: another conflict, or a git call that fails, stops the round.

Tier 1 runs code of the checkout of the pull request: `devops docs generate` and `uv lock` start
the project and its build hooks. So `run_fix_conflict` rebases only with `confirm`, which the
command gives only in a runner Job (`require_runner`), after the Job makes its process unreadable
and adopts the orphans of that code, as fix-checks does. Without `confirm`, as on a workstation,
the step returns `planned`: it runs no code of the checkout, pushes nothing and writes no record.
The step works in a full clone in a new folder of the run (`ensure_checkout`), reads the URL of
`origin` before tier 1 runs, and pushes through `OriginGit` to that URL, with a lease on the judged
head.

Stops immediately if a release path (CHANGELOG.md, manifests, version lines) conflicts.
Enforces safety bounds: bot pull requests only, no human commits after bot push, no human claims
or owner/* labels, soft cap 2 rounds (extendable to 3 if conflicted files decrease), hard cap 4.
Runs `openspec validate --specs --strict` before pushing.
"""

from __future__ import annotations

import json
import logging
import re
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
    CONST_GIT_NO_EDITOR_CONFIG,
    CONST_GIT_REMOTE_ORIGIN,
)
from devops_cli.config.settings import RoadmapFixConflictConfig, load_settings
from devops_cli.core.process import run_subprocess
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.exceptions import GitOperationError
from devops_cli.exceptions.roadmap import RoadmapImplementError
from devops_cli.git.branch_authors import LOG_FORMAT, person_authors
from devops_cli.git.branch_form import parse_branch
from devops_cli.github.client import PullStatus
from devops_cli.github.session import get_github_session
from devops_cli.roadmap.claim import claim_labels, claimed_by
from devops_cli.roadmap.implement.git_isolation import OriginGit, origin_url
from devops_cli.roadmap.implement.implement_step import find_change
from devops_cli.roadmap.run import ensure_checkout
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
# A commit whose paths are all under these folders or generated documents is an archive commit,
# which tier 1 drops at a stop and writes again.
_ARCHIVE_ROOTS: Final[tuple[str, ...]] = ("openspec/changes/", "openspec/specs/")
_NOT_SETTLED: Final[str] = "Conflict could not be resolved by Tier 1"
_RUNNER_NOTE: Final[str] = (
    "Tier 1 runs code of the pull request (`devops docs generate`, `uv lock`), so it runs only "
    "with --confirm in a runner Job."
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


def _merge_tree(cwd: Path, base_ref: str, head_ref: str) -> tuple[str, list[str]] | None:
    """The tree that `git merge-tree` writes for the merge of `head_ref` into `base_ref`, and its
    conflicted paths; None for a merge with no conflict."""
    proc = run_subprocess(
        [
            CONST_GIT_CLI,
            "-C",
            str(cwd),
            "merge-tree",
            "--write-tree",
            "--name-only",
            "--no-messages",
        ]
        + ["-z", base_ref, head_ref],
        check=False,
        quiet=True,
    )
    if proc.returncode == 0:
        return None
    if proc.returncode != 1:
        raise GitOperationError(
            f"git merge-tree failed: {proc.stderr.strip() or proc.stdout.strip()}",
            operation=_GIT_OPERATION,
        )
    tree, *paths = [field for field in proc.stdout.split("\0") if field]
    return tree, sorted(set(paths))


def check_merge_tree_conflict(cwd: Path, base_ref: str, head_ref: str) -> tuple[bool, list[str]]:
    """Check whether merging head_ref into base_ref causes merge conflicts (#5019)."""
    merged = _merge_tree(cwd, base_ref, head_ref)
    return (False, []) if merged is None else (True, merged[1])


def release_conflict(cwd: Path, base_ref: str, head_ref: str) -> bool:
    """Whether the merge of `head_ref` into `base_ref` conflicts on release metadata (#5019): a
    release path, or a version line on the side of `head_ref` in a conflict, which `git diff`
    shows as an added line during the rebase (`is_release_path`). The plan and the round both ask
    it, so the plan says what the round does."""
    merged = _merge_tree(cwd, base_ref, head_ref)
    if merged is None:
        return False
    tree, paths = merged
    for path in paths:
        blob = run_subprocess(
            [CONST_GIT_CLI, "-C", str(cwd), "cat-file", "-p", f"{tree}:{path}"],
            check=False,
            quiet=True,
        )
        theirs, added = False, []
        for line in blob.stdout.splitlines() if blob.returncode == 0 else []:
            if line.startswith(("=======", ">>>>>>>")):
                theirs = line.startswith("=")
            elif theirs:
                added.append(f"+ {line}")
        if is_release_path(path, "\n".join(added)):
            return True
    return False


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
    """Whether a bot wrote each commit of `head_ref` past `base_ref` (#5019). A clean merge, such as
    a merge of the default branch, counts for no author (`person_authors`)."""
    log = _git(cwd, "log", LOG_FORMAT, f"{base_ref}..{head_ref}")
    return all(
        _is_bot_author(author) for author in person_authors([CONST_GIT_CLI, "-C", str(cwd)], log)
    )


def _archive_again(cwd: Path, item_number: int) -> bool:
    """Generate the documents and archive the change again from the active change folder, in a
    commit of its own (#5019)."""
    try:
        active_change = find_change(cwd, item_number, archived=False)
    except FileNotFoundError, ValueError, RoadmapImplementError:
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


def _is_archive_commit(cwd: Path, item_number: int) -> bool:
    """Whether the commit that the rebase stopped on is the archive commit of the item: it moves
    `openspec/changes/<item>-*/` away, and each of its paths is an OpenSpec path or a generated
    document. Another commit, or one that also holds code, is no commit to drop."""
    listed = _git(cwd, "show", "--name-status", "--format=", "REBASE_HEAD").splitlines()
    entries = [line.split("\t") for line in listed if line]
    folder = f"openspec/changes/{item_number}-"
    paths = [path for entry in entries for path in entry[1:]]
    return any(entry[0][:1] in "DR" and entry[1].startswith(folder) for entry in entries) and all(
        path.startswith(_ARCHIVE_ROOTS) or is_generated_docs_path(path) for path in paths
    )


def _take_default_branch(cwd: Path, path: str) -> None:
    """Take the side of the default branch for a conflicted path, as a developer does: its file,
    or no file when the default branch deleted it (`git status` shows `D` first)."""
    if _git(cwd, "status", "--porcelain", "--", path).startswith("D"):
        _git(cwd, "rm", "-q", "--", path)
    else:
        _git(cwd, "checkout", "--ours", "--", path)
        _git(cwd, "add", "--", path)


def resolve_tier1(cwd: Path, item_number: int, message: str = "") -> str | None:
    """Settle each stop of the rebase in `cwd` with no model call (#5019), then make again what
    tier 1 took from the default branch: the lockfile, the generated documents and the archive of
    the change, the archive last. None when the rebase ended so, else the reason of the stop. A stop
    leaves the rebase to the caller. `message` is the last line of git for a rebase that stopped
    with no conflicted file."""
    remade: set[str] = set()
    while conflicts := conflicted_files(cwd):
        generated = [c for c in conflicts if is_generated_docs_path(c) or is_lockfile_path(c)]
        archived = [c for c in conflicts if c not in generated]
        if archived and not (
            all(is_archive_path(c) for c in archived) and _is_archive_commit(cwd, item_number)
        ):
            return _NOT_SETTLED
        for c in generated:
            _take_default_branch(cwd, c)
            remade.add("lock" if is_lockfile_path(c) else "docs")
        args: tuple[str, ...] = ("-c", CONST_GIT_NO_EDITOR_CONFIG, "rebase", "--continue")
        if archived:
            remade.add("archive")
            args = ("rebase", "--skip")
        proc = run_subprocess([CONST_GIT_CLI, "-C", str(cwd), *args], check=False, quiet=True)
        if proc.returncode == 0:
            break
        lines = (proc.stderr.strip() or proc.stdout.strip()).splitlines()
        message = mask_secrets(lines[-1]) if lines else f"exit {proc.returncode}"
    else:
        return f"The rebase failed with no conflicted file: {message or 'no output'}"
    if "lock" in remade and not _regenerate_lock_and_commit(cwd, item_number):
        return "uv lock failed"
    if "archive" in remade:
        return (
            None if _archive_again(cwd, item_number) else "The change could not be archived again"
        )
    if "docs" in remade and not _regenerate_docs_and_commit(cwd, item_number):
        return "devops docs generate failed"
    return None


def _plan_reason(conflicts: Sequence[str], tier1_mode: str, release: bool) -> str:
    """What a confirmed round would do with the conflicted paths `conflicts`, by the rules of tier
    1. `release` is the answer of `release_conflict`."""
    if tier1_mode != "on":
        action = "stop, because roadmap.fix_conflict.tier1_mode is not on"
    elif release:
        action = "stop on the release path"
    elif all(is_archive_path(path) for path in conflicts):
        action = (
            "drop an archive commit that holds only OpenSpec paths and generated documents, "
            "rebase and archive the change again with tier 1"
        )
    elif all(is_generated_docs_path(path) or is_lockfile_path(path) for path in conflicts):
        action = "take the default branch for these files and generate them again with tier 1"
    else:
        action = (
            "stop, because tier 1 settles only archive, generated document and lockfile conflicts"
        )
    return f"Plan: {action}. {_RUNNER_NOTE}"


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

    # The tip of the branch before the rebase, which a failed round gives back.
    tip = _git(cwd, "rev-parse", "ORIG_HEAD")
    try:
        settled = (
            not release_conflict(cwd, f"origin/{default_branch}", tip)
            and resolve_tier1(cwd, item) is None
            and validate_strict_specs(cwd)
        )
    except GitOperationError as exc:
        logger.warning("Tier 1 failed: %s", exc)
        settled = False
    if settled:
        _record_fix_conflict_marks(
            store, item, rounds=1, files=[], result=FixConflictResult.RESOLVED
        )
        return True

    _abort_rebase(cwd)
    _git(cwd, "reset", "--hard", tip)
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
    conflicts: Sequence[str],
    release: bool,
    current_rounds: int,
) -> FixConflictReport:
    reason: str | None = "Conflict on a release path" if release else _NOT_SETTLED
    try:
        if not release:
            _git(worktree, "switch", "-C", status.head_ref, head_ref)
            proc = run_subprocess(
                [CONST_GIT_CLI, "-C", str(worktree), "rebase", base_ref], check=False, quiet=True
            )
            lines = (proc.stderr.strip() or proc.stdout.strip()).splitlines()
            if proc.returncode == 0:
                reason = None
            elif settings.tier1_mode == "on":
                reason = resolve_tier1(
                    worktree, item_num or pull, mask_secrets(lines[-1]) if lines else ""
                )
    except GitOperationError as exc:
        reason = mask_secrets(str(exc))

    if reason is not None:
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
        return FixConflictReport(
            repo=repo,
            pull=pull,
            result=FixConflictResult.FAILED,
            head=status.head_sha,
            rounds=current_rounds + 1,
            reason="openspec validate --specs --strict failed",
        )

    # Never push the tip of the default branch over the pull request.
    if _git(worktree, "rev-list", "--count", f"{base_ref}..HEAD") == "0":
        return FixConflictReport(
            repo=repo,
            pull=pull,
            result=FixConflictResult.FAILED,
            head=status.head_sha,
            rounds=current_rounds + 1,
            reason=f"The rebase left no commit past {base_ref}",
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

    release = release_conflict(worktree, base_ref, head_ref)
    if not confirm:
        return FixConflictReport(
            repo=repo,
            pull=pull,
            result=FixConflictResult.PLANNED,
            head=status.head_sha,
            rounds=current_rounds,
            files=tuple(initial_conflicts),
            reason=_plan_reason(initial_conflicts, settings.tier1_mode, release),
        )

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
        conflicts=initial_conflicts,
        release=release,
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
    with tempfile.TemporaryDirectory(prefix="devops-fix-conflict-") as root:
        try:
            worktree = source or ensure_checkout(repo, Path(root))
        except GitOperationError as exc:
            return FixConflictReport(
                repo=repo,
                pull=pull,
                result=FixConflictResult.FAILED,
                head=status.head_sha,
                reason=str(exc),
            )
        # The URL of `origin`, read before tier 1 runs code of the pull request.
        origin = OriginGit(worktree, origin_url(worktree))
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


def dry_run_fix_conflict(
    repo: str, pull: int
) -> tuple[tuple[PlannedRequest, ...], tuple[PlannedRequest, ...]]:
    """Dry-run planned requests for fix-conflict (ADR 0021; #5019). Sees 0 requests."""
    return (), ()
