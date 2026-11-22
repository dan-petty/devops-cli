"""The roadmap step `fix-conflict`: settles merge conflicts on open bot pull requests (ADR 0021,
section 8; #5019).

Tier 1 (deterministic, no model) settles each stop of the rebase onto the default branch with the
shared rules of `roadmap/phases/rebase.py`, as implement and fix-checks do. It takes the side of
the default branch for generated documents and `uv.lock` (`git checkout --ours`, or `git rm` when
that side has no file) and makes them again at that stop. It drops only the archive commit of the
item, which touches no other change (`git rebase --skip`), and archives the change again after the
rebase, in a commit of its own. Tier 2 (model) is not built: another conflict stops the round. Each
round that reaches the agent phase counts in the record, which `prepare` writes before the agent
runs; one that does not end `resolved`, also on an error, aborts the rebase and gives the clone back
the judged head. A failed program of tier 1 gives its exit status and the end of its output in the
reason of the stop.

The round runs on the phases `prepare`, `agent` and `publish` (`fix_conflict_phases.py`, #6703).
This module holds the admission (`admit_round`), the release rule, the caps, the plan and the
record. Tier 1 runs code of the checkout of the pull request: `devops docs generate` and `uv lock`
start the project and its build hooks. So it runs only with `confirm`, in the agent phase, which
the command runs only in a runner Job, after the Job makes its process unreadable and adopts the
orphans of that code, as fix-checks does. Without `confirm`, as on a workstation, the round ends in
`prepare` with `planned`: it runs no code of the checkout, pushes nothing and writes no record.

Stops immediately if a release path conflicts: CHANGELOG.md, a file of release-please, or the
version line of pyproject.toml (#6623).
Enforces safety bounds: bot pull requests only, no human claims or owner/* labels, soft cap 2
rounds (extendable to 3 if conflicted files decrease), hard cap 4. With `confirm`, a commit past the
default branch that the App did not write fails the round (`clone_branch`).
Runs `openspec validate --specs --strict` before pushing.
"""

from __future__ import annotations

import json
import logging
import re
import shlex
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Final

from devops_cli.config.commands import BIN_OPENSPEC, BIN_UV
from devops_cli.config.constants import (
    CONST_CHANGELOG_FILENAME,
    CONST_GIT_CLI,
    CONST_PYPROJECT_FILENAME,
)
from devops_cli.config.settings import RoadmapFixConflictConfig, load_settings
from devops_cli.core.process import run_subprocess
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.exceptions import GitOperationError
from devops_cli.exceptions.roadmap import RoadmapImplementError
from devops_cli.git.branch_form import parse_branch
from devops_cli.github.client import PullStatus
from devops_cli.github.session import get_github_session
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.claim import claim_labels, claimed_by
from devops_cli.roadmap.implement.implement_step import output_tail
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
NOT_SETTLED: Final[str] = "Conflict could not be resolved by Tier 1"
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


def _is_bot_author(author: str) -> bool:
    if not author:
        return False
    if author.endswith(_BOT_SUFFIX):
        return True
    bot = load_settings().service.github_app.bot_login
    return bool(bot and author == bot)


def admission_bounds(
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


def _tier1_kind(conflicts: Sequence[str]) -> str:
    """How tier 1 settles a stop or a plan on the conflicted paths `conflicts`: `generated` when
    each is a generated document or `uv.lock`, `archive` when the others are archive paths, else
    `stop`. The plan and the round both ask it."""
    others = [c for c in conflicts if not (is_generated_docs_path(c) or is_lockfile_path(c))]
    if not others:
        return "generated"
    return "archive" if all(is_archive_path(c) for c in others) else "stop"


def plan_reason(conflicts: Sequence[str], tier1_mode: str, release: bool) -> str:
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


def record_fix_conflict_marks(
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


def read_item_conflict_state(item: Item | None) -> tuple[int, list[str]]:
    if item is None:
        return 0, []
    record = item.job_record
    rounds = int(record.get(FixConflictRecordKey.ROUNDS) or "0")
    try:
        files = json.loads(record.get(FixConflictRecordKey.FILES) or "[]")
    except json.JSONDecodeError, TypeError, ValueError:
        files = []
    return rounds, files


def check_conflict_caps(
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


@dataclass(frozen=True)
class ConflictRound:
    """A round that passed the admission (#5019): the pull request as GitHub holds it, its item,
    the settings of the step, and the rounds and the files that the record holds."""

    repo: str
    pull: int
    status: PullStatus
    item_num: int | None
    item: Item | None
    settings: RoadmapFixConflictConfig
    rounds: int
    prev_files: list[str]

    def report(
        self,
        result: FixConflictResult,
        reason: str,
        *,
        head: str = "",
        rounds: int | None = None,
        files: Sequence[str] = (),
    ) -> FixConflictReport:
        """The report of the round, on the judged head unless `head` names the pushed one."""
        return FixConflictReport(
            repo=self.repo,
            pull=self.pull,
            result=result,
            head=head or self.status.head_sha,
            rounds=self.rounds if rounds is None else rounds,
            files=tuple(files),
            reason=reason,
        )


def admit_round(
    store: RoadmapStore, client: Any, repo: str, pull: int, *, head: str | None
) -> ConflictRound | FixConflictReport:
    """The admission of a round on pull request `pull`, with no clone: the bounds of the step
    (`admission_bounds`) and the hard cap of the rounds. The report of a round that ends here."""
    status: PullStatus = client.get_pull_status(repo, pull)
    parts = parse_branch(status.head_ref)
    item_num = parts.issue if parts else None
    item = store.item(item_num) if item_num else None
    if refused := admission_bounds(status, item, expected_head=head):
        logger.info("fix-conflict refused PR #%d: %s", pull, refused)
        return FixConflictReport(
            repo=repo,
            pull=pull,
            result=FixConflictResult.REFUSED,
            head=status.head_sha,
            reason=refused,
        )
    settings = load_settings().roadmap.fix_conflict
    rounds, prev_files = read_item_conflict_state(item)
    judged = ConflictRound(repo, pull, status, item_num, item, settings, rounds, prev_files)
    if rounds >= settings.hard_cap_rounds:
        return judged.report(
            FixConflictResult.STOPPED, f"Hard cap reached ({settings.hard_cap_rounds} rounds)"
        )
    return judged


def run_program(cwd: Path, argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """Run a program of tier 1 in the checkout `cwd`, which runs code of the pull request. The log
    names the program and its exit status, and no output of it: the output goes only into the
    stop of the round (`tier1_failure`)."""
    proc = run_subprocess(list(argv), cwd=cwd, check=False, quiet=True)
    if proc.returncode != 0:
        logger.warning("%s exited %d", " ".join(argv[:5]), proc.returncode)
    return proc


def tier1_failure(
    argv: Sequence[str], done: subprocess.CompletedProcess[str]
) -> RoadmapImplementError:
    """The stop of a round whose program of tier 1 failed: what tier 1 made again, and the exit
    status and the last lines of the output, as implement gives them (`output_tail`). The round
    masks the reason before it writes it."""
    words = list(argv)
    if words[:2] == [BIN_UV, "lock"]:
        lead = "uv lock failed"
    elif words[-2:] == ["docs", "generate"]:
        lead = "devops docs generate failed"
    elif "archive" in words:
        lead = "The change could not be archived again"
    else:
        lead = f"`{' '.join(words[:5])}` failed"
    detail = MESSAGES.roadmap.implement_stop_program_failed.format(
        command=shlex.join(words), status=done.returncode, output=output_tail(done)
    )
    return RoadmapImplementError(f"{lead}: {detail}")


def run_fix_conflict(
    store: RoadmapStore,
    repo: str,
    pull: int,
    *,
    head: str | None = None,
    confirm: bool = False,
) -> FixConflictReport:
    """Execute the fix-conflict step on pull request `pull` (#5019): the admission, then the three
    phases in one process (`repair_round`, #6703). Without `confirm` the round ends in `prepare`
    with its plan, runs no code of the checkout and writes nothing. With `confirm` the agent phase
    rebases and runs tier 1, which runs code of the pull request, and `publish` pushes: only a
    runner Job passes it, after `require_runner` and the hardening of its process, as the command
    does."""
    from devops_cli.roadmap.steps.fix_conflict_phases import repair_round

    client = get_github_session().client
    judged = admit_round(store, client, repo, pull, head=head)
    if isinstance(judged, FixConflictReport):
        return judged
    return repair_round(store, client, judged, confirm=confirm)


def dry_run_fix_conflict(
    repo: str, pull: int
) -> tuple[tuple[PlannedRequest, ...], tuple[PlannedRequest, ...]]:
    """Dry-run planned requests for fix-conflict (ADR 0021; #5019). Sees 0 requests."""
    return (), ()
