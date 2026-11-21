"""The roadmap step `fix-conflict`: settles merge conflicts on open bot pull requests (ADR 0021,
section 8; #5019).

Tier 1 (deterministic, no model) settles each stop of the rebase onto the default branch. It takes
the side of the default branch for generated documents and `uv.lock` (`git checkout --ours`, or
`git rm` when that side has no file), and runs `devops docs generate` and `uv lock` after the
rebase. It drops only the archive commit of the item, which moves its change folder into the
archive and touches no other change (`git rebase --skip`), and archives the change again after the
rebase, in a commit of its own. Tier 2 (model) is not built: another conflict stops the round. A
round (`_round`) counts in the record; one that does not end `resolved`, also on an error, aborts
the rebase and gives the branch back its tip.

Tier 1 runs code of the checkout of the pull request: `devops docs generate` and `uv lock` start
the project and its build hooks. So `run_fix_conflict` rebases only with `confirm`, which the
command gives only in a runner Job (`require_runner`), after the Job makes its process unreadable
and adopts the orphans of that code, as fix-checks does. Without `confirm`, as on a workstation,
the step returns `planned`: it runs no code of the checkout, pushes nothing and writes no record.
The step works in a full clone in a new folder of the run (`ensure_checkout`), reads the URL of
`origin` before tier 1 runs, and pushes through `OriginGit` to that URL, with a lease on the judged
head.

Stops immediately if a release path conflicts: CHANGELOG.md, a file of release-please, or the
version line of pyproject.toml (#6623).
Enforces safety bounds: bot pull requests only, no human commits after bot push, no human claims
or owner/* labels, soft cap 2 rounds (extendable to 3 if conflicted files decrease), hard cap 4.
Runs `openspec validate --specs --strict` before pushing.
"""

from __future__ import annotations

import json
import logging
import re
import tempfile
from collections.abc import Callable, Sequence
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
    CONST_OPENSPEC_ARCHIVE_DIR,
    CONST_OPENSPEC_ARCHIVED_FOLDER_RE,
    CONST_OPENSPEC_CHANGE_FOLDER_RE,
    CONST_OPENSPEC_CHANGES_DIR,
    CONST_PYPROJECT_FILENAME,
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
    """Whether a conflict on `path` changes release metadata (#5019, #6623): `CHANGELOG.md`, a file
    of release-please, or the version line of `pyproject.toml` in `diff_text`. The `version =` line
    of a package in `uv.lock` is none: tier 1 takes the `uv.lock` of the default branch and runs
    `uv lock` again."""
    if path in _RELEASE_PATHS or path.startswith(".release-please"):
        return True
    return path == CONST_PYPROJECT_FILENAME and bool(
        re.search(r"^[+-]\s*version\s*=\s*", diff_text, re.MULTILINE)
    )


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
    release path, or the version line of `pyproject.toml` on the side of `head_ref` in a conflict,
    which `git diff` shows as an added line during the rebase (`is_release_path`). The plan and
    the round both ask it, so the plan says what the round does."""
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


def _tier1_kind(conflicts: Sequence[str]) -> str:
    """How tier 1 settles a stop or a plan on the conflicted paths `conflicts`: `generated` when
    each is a generated document or `uv.lock`, `archive` when the others are archive paths, else
    `stop`. The plan and the round both ask it."""
    others = [c for c in conflicts if not (is_generated_docs_path(c) or is_lockfile_path(c))]
    if not others:
        return "generated"
    return "archive" if all(is_archive_path(c) for c in others) else "stop"


def _change_issue(path: str) -> str | None:
    """The issue of the change folder, active or archived, that holds `path`, or None."""
    for pattern in (CONST_OPENSPEC_ARCHIVED_FOLDER_RE, CONST_OPENSPEC_CHANGE_FOLDER_RE):
        if found := re.fullmatch(pattern, path):
            return found["issue"]
    return None


def _is_archive_commit(cwd: Path, item_number: int) -> bool:
    """Whether the commit that the rebase stopped on is the archive commit of the item: it moves
    `openspec/changes/<item>-*/` away, each of its paths is an OpenSpec path or a generated
    document, and each path under `openspec/changes/` belongs to the change of the item."""
    listed = _git(cwd, "show", "--name-status", "--format=", "REBASE_HEAD").splitlines()
    entries = [line.split("\t") for line in listed if line]
    item = str(item_number)
    moves = any(
        entry[0][:1] in "DR"
        and not entry[1].startswith(f"{CONST_OPENSPEC_ARCHIVE_DIR}/")
        and _change_issue(entry[1]) == item
        for entry in entries
    )
    paths = [path for entry in entries for path in entry[1:]]
    return moves and all(
        (path.startswith(_ARCHIVE_ROOTS) or is_generated_docs_path(path))
        and (not path.startswith(f"{CONST_OPENSPEC_CHANGES_DIR}/") or _change_issue(path) == item)
        for path in paths
    )


def _take_default_branch(cwd: Path, path: str) -> None:
    """Take the side of the default branch for a conflicted path, as a developer does: its file,
    or no file when the default branch has none (no stage 2 in the index: `DU`, `DD`, `UA`)."""
    stages = {line.split()[2] for line in _git(cwd, "ls-files", "-u", "--", path).splitlines()}
    if "2" in stages:
        _git(cwd, "checkout", "--ours", "--", path)
        _git(cwd, "add", "--", path)
    else:
        _git(cwd, "rm", "-q", "--", path)


def _stopped_on(cwd: Path) -> str:
    """The commit that the rebase stopped on, or "" when it stopped on none."""
    proc = run_subprocess(
        [CONST_GIT_CLI, "-C", str(cwd), "rev-parse", "-q", "--verify", "REBASE_HEAD"],
        check=False,
        quiet=True,
    )
    return proc.stdout.strip()


def resolve_tier1(cwd: Path, item_number: int, message: str = "") -> str | None:
    """Settle each stop of the rebase in `cwd` with no model call (#5019), then make again what
    tier 1 took from the default branch (`_make_again`). None when the rebase ended so, else the
    reason of the stop. Each
    `--skip` or `--continue` moves the rebase on, or raises `GitOperationError`. `message` is the
    last line of git for a rebase that stopped with no conflicted file."""
    remade: set[str] = set()
    while conflicts := conflicted_files(cwd):
        kind = _tier1_kind(conflicts)
        if kind == "stop" or (kind == "archive" and not _is_archive_commit(cwd, item_number)):
            return _NOT_SETTLED
        for c in conflicts:
            if is_generated_docs_path(c) or is_lockfile_path(c):
                _take_default_branch(cwd, c)
                remade.add("lock" if is_lockfile_path(c) else "docs")
        args: tuple[str, ...] = ("-c", CONST_GIT_NO_EDITOR_CONFIG, "rebase", "--continue")
        if kind == "archive":
            remade.add("archive")
            args = ("rebase", "--skip")
        stopped = _stopped_on(cwd)
        proc = run_subprocess([CONST_GIT_CLI, "-C", str(cwd), *args], check=False, quiet=True)
        if proc.returncode == 0:
            break
        lines = (proc.stderr.strip() or proc.stdout.strip()).splitlines()
        message = mask_secrets(lines[-1]) if lines else f"exit {proc.returncode}"
        if _stopped_on(cwd) == stopped:
            raise GitOperationError(
                f"git {' '.join(args[-2:])} failed: {message}", operation=_GIT_OPERATION
            )
    else:
        return f"The rebase failed with no conflicted file: {message or 'no output'}"
    return _make_again(cwd, item_number, remade)


def _make_again(cwd: Path, item_number: int, remade: set[str]) -> str | None:
    """Make again what tier 1 took from the default branch: the lockfile, the generated documents
    and the archive of the change, the archive last. None, or the reason of a failure."""
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
    1 (`_tier1_kind`). `release` is the answer of `release_conflict`."""
    kind = _tier1_kind(conflicts)
    if tier1_mode != "on":
        action = "stop, because roadmap.fix_conflict.tier1_mode is not on"
    elif release:
        action = "stop on the release path"
    elif kind == "archive":
        action = (
            "drop the archive commit of the item if that commit conflicts, take the default "
            "branch for generated documents and uv.lock, and archive the change again with tier "
            "1; another conflicting OpenSpec commit stops the round"
        )
    elif kind == "generated":
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


def _round(
    cwd: Path,
    base_ref: str,
    tip: str,
    settle: Callable[[], str | None],
    *,
    store: RoadmapStore | None,
    item: int | Item | None,
    files: Sequence[str],
    key: str | None = None,
    push: Callable[[str], None] | None = None,
) -> tuple[FixConflictResult, str, int]:
    """One confirmed round of tier 1 in `cwd` (#5019): `settle` rebases and settles each stop (None,
    or the reason of a stop), then the strict validation, the check that a commit is past
    `base_ref`, and `push` of the result. Every round counts in the record. A round that does not
    end `resolved`, also on an error, aborts the rebase and resets the branch to `tip` first. An
    error of git is a stop; any other error goes on after that. The result, its reason, and the
    rounds."""
    if isinstance(item, int):
        item = store.item(item) if store is not None else None
    rounds = _read_item_conflict_state(item)[0] + 1
    result, reason = FixConflictResult.FAILED, "The round ended with an error"
    try:
        stop = settle()
        if stop is not None:
            result, reason = FixConflictResult.STOPPED, stop
        elif not validate_strict_specs(cwd):
            reason = "openspec validate --specs --strict failed"
        elif _git(cwd, "rev-list", "--count", f"{base_ref}..HEAD") == "0":
            # Never push the tip of the default branch over the pull request.
            reason = f"The rebase left no commit past {base_ref}"
        else:
            if push is not None:
                push(_git(cwd, "rev-parse", "HEAD"))
            result, reason = FixConflictResult.RESOLVED, ""
    except GitOperationError as exc:
        result, reason = FixConflictResult.STOPPED, mask_secrets(str(exc))
    finally:
        resolved = result is FixConflictResult.RESOLVED
        if not resolved:
            _abort_rebase(cwd)
            _git(cwd, "reset", "--hard", tip)
        _record_fix_conflict_marks(
            store, item, key=key, rounds=rounds, files=[] if resolved else files, result=result
        )
    return result, reason, rounds


def fix_rebase_conflict(
    cwd: Path,
    *,
    repo: str,
    item: int,
    default_branch: str,
    store: RoadmapStore | None = None,
) -> bool:
    """Programmatic helper for implement runner Job on rebase conflict (#5019).

    Attempts Tier 1 deterministic settlement in one round (`_round`). Returns True if resolved
    cleanly, or False if conflict requires human/model intervention; then the branch is back on
    its tip from before the rebase.
    """
    conflicts = conflicted_files(cwd)
    if not conflicts:
        return False
    base_ref = f"origin/{default_branch}"
    tip = _git(cwd, "rev-parse", "ORIG_HEAD")

    def settle() -> str | None:
        if release_conflict(cwd, base_ref, tip):
            return "Conflict on a release path"
        return resolve_tier1(cwd, item)

    result, _, _ = _round(cwd, base_ref, tip, settle, store=store, item=item, files=conflicts)
    if result is not FixConflictResult.RESOLVED:
        logger.warning("Tier 1 did not settle the rebase: %s", result.value)
    return result is FixConflictResult.RESOLVED


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
) -> FixConflictReport:
    def settle() -> str | None:
        _git(worktree, "switch", "-C", status.head_ref, head_ref)
        if release:
            return "Conflict on a release path"
        proc = run_subprocess(
            [CONST_GIT_CLI, "-C", str(worktree), "rebase", base_ref], check=False, quiet=True
        )
        if proc.returncode == 0:
            return None
        if settings.tier1_mode != "on":
            return _NOT_SETTLED
        lines = (proc.stderr.strip() or proc.stdout.strip()).splitlines()
        return resolve_tier1(worktree, item_num or pull, mask_secrets(lines[-1]) if lines else "")

    def push(head: str) -> None:
        origin.push(status.head_ref, head, lease=status.head_sha)

    key = f"{_git(worktree, 'rev-parse', base_ref)}:{status.head_sha}"
    result, reason, rounds = _round(
        worktree,
        base_ref,
        head_ref,
        settle,
        store=store,
        item=item,
        files=conflicts,
        key=key,
        push=push,
    )
    resolved = result is FixConflictResult.RESOLVED
    return FixConflictReport(
        repo=repo,
        pull=pull,
        result=result,
        head=_git(worktree, "rev-parse", "HEAD") if resolved else status.head_sha,
        rounds=rounds,
        files=() if resolved else tuple(conflicts),
        reason=reason,
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
