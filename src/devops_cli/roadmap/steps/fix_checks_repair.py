"""The repair that the step `fix-checks` uses in a runner Job (#5971).

The command `devops roadmap step fix-checks --confirm` gives the step `job_repair`:

- The checkout: a worktree of the clone `model-clone` on the head branch of the pull request,
  taken over from `origin` with `add_worktree` and `OriginGit`, as the implement job takes over a
  staged branch. The App must have written every commit of the branch past main. The push sends
  the new commits to the head branch with a lease on the judged head, so it never overwrites a push
  of another writer. The worktree and its local branch go when the round ends.
- Tier 1, with no model: for a lint failure, `ruff check --fix` and `ruff format` on the Python
  files that the pull request changes (a toolchain with the ruff gates); for a snapshot failure,
  the snapshot update of the toolchain on the tests whose snapshot differs (#6116); for a lint, a
  docs or a snapshot failure, `devops docs generate` (a toolchain with the docs step); and for a
  lockfile failure, `uv lock`. A docs, a lockfile or a snapshot failure starts tier 1 in a check of
  any class (#5983). It commits the tracked files that the fixers changed, and names them.
- Tier 2: the fix step of the implement job (`run_fix_step`) on the model of the task
  `ai.tasks.fix_checks`, with no ladder, the hooks and the recorded tests of the default branch,
  and the cap `roadmap.fix_checks.token_budget` of new tokens. The step may also change the files
  outside the plan whose failure the change of the branch causes (#6116).
"""

from __future__ import annotations

import logging
import shlex
import subprocess
from collections.abc import Iterator, Sequence
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from devops_cli.ai.client.factory import get_task_model
from devops_cli.config.commands import BIN_DEVOPS, BIN_RUFF, BIN_UV
from devops_cli.config.settings import load_settings
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions.roadmap import RoadmapImplementError
from devops_cli.git.worktree_add import add_worktree
from devops_cli.github.client import PullStatus
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.clone_git import default_branch, git
from devops_cli.roadmap.implement.git_isolation import OriginGit, origin_url
from devops_cli.roadmap.implement.implement_hooks import install_hook_environments, trusted_config
from devops_cli.roadmap.implement.implement_limits import TokenCap
from devops_cli.roadmap.implement.implement_step import (
    FixRequest,
    ItemReader,
    StepStatus,
    run_fix_step,
)
from devops_cli.roadmap.plan_read import PlanReadError, merged_recorded_tests
from devops_cli.roadmap.project_profile import resolve_profile
from devops_cli.roadmap.run import model_clone
from devops_cli.roadmap.steps.fix_checks import (
    Fixed,
    ModelFixer,
    PullCheckout,
    Repair,
    Tier1Causes,
    tier1_causes,
)
from devops_cli.roadmap.toolchains import ToolchainPreset

logger = logging.getLogger(__name__)

# The operation that a failed git call of the step names.
_OPERATION: Final[str] = "roadmap.fix_checks"
# The task of the model fix, and the setting of its cap (#5971).
_TASK: Final[str] = "fix_checks"
_CAP_SETTING: Final[str] = "roadmap.fix_checks.token_budget"
# The toolchain gates that run ruff, as the implement step reads them.
_RUFF_GATES: Final[str] = "ruff-mypy"
_LOCK_FILE: Final[str] = "uv.lock"


@dataclass(frozen=True)
class WorktreeCheckout:
    """The worktree on the head branch `branch` at the judged head `judged`, and the git calls of
    the job that reach `origin`."""

    path: Path
    branch: str
    judged: str
    origin: OriginGit

    def push(self) -> str | None:
        """Push `HEAD` to the head branch with a lease on the judged head: the new head, or None
        when `HEAD` is the judged head."""
        tip = git(self.path, "rev-parse", "HEAD", operation=_OPERATION)
        if tip == self.judged:
            return None
        self.origin.push(self.branch, tip, lease=self.judged)
        return tip


@contextmanager
def pull_checkout(
    repo: str, status: PullStatus, item: int, source: Path | None = None
) -> Iterator[WorktreeCheckout]:
    """The worktree of the clone `source`, or of the clone `model-clone` of `repo`, on the head
    branch of the pull request of `status`, the branch of `item`. The take-over refuses a branch
    with a commit past main that the App did not write. The worktree must be on the head branch of
    the pull request and at its judged head."""
    source = source or model_clone(repo)
    url = origin_url(source)
    report = add_worktree(source, issue=item, origin=OriginGit(source, url))
    path = Path(report.path)
    try:
        if report.branch != status.head_ref:
            raise RoadmapImplementError(
                f"The branch of item #{item} is `{report.branch}`, not the head branch "
                f"`{status.head_ref}` of the pull request."
            )
        tip = git(path, "rev-parse", "HEAD", operation=_OPERATION)
        if tip != status.head_sha:
            raise RoadmapImplementError(
                f"The head branch `{report.branch}` is at {tip[:12]}, not at the judged head "
                f"{status.head_sha[:12]}."
            )
        (path / ".data" / "agent" / "scratch").mkdir(parents=True, exist_ok=True)
        yield WorktreeCheckout(path, report.branch, status.head_sha, OriginGit(path, url))
    finally:
        git(source, "worktree", "remove", "--force", str(path), operation=_OPERATION)
        git(source, "branch", "-D", report.branch, operation=_OPERATION)


def _base(path: Path) -> str:
    return f"origin/{default_branch(path, operation=_OPERATION)}"


def _changed_python_files(path: Path, base: str) -> list[str]:
    """The Python files that the pull request adds or changes, as regular files. A link is left
    out, so a fixer never writes through it."""
    listed = git(
        path,
        "diff",
        "--name-only",
        "--diff-filter=ACMR",
        "-z",
        f"{base}...HEAD",
        operation=_OPERATION,
    )
    return [
        name
        for name in listed.split("\0")
        if name.endswith((".py", ".pyi"))
        and not (path / name).is_symlink()
        and (path / name).is_file()
    ]


@dataclass(frozen=True)
class Tier1Commands:
    """The fixers of tier 1 for the causes of a failure, and the checks that run again after their
    commit."""

    fixes: tuple[tuple[str, ...], ...]
    checks: tuple[tuple[str, ...], ...]


def _with_tests(argv: Sequence[str], tests: Sequence[str]) -> tuple[str, ...]:
    """The command `argv` with the word `{tests}` replaced by the test files `tests`."""
    return tuple(word for part in argv for word in (tests if part == "{tests}" else (part,)))


def tier1_commands(
    path: Path, preset: ToolchainPreset, files: Sequence[str], causes: Tier1Causes
) -> Tier1Commands:
    """The fixers of tier 1 for `causes` in the checkout `path`, and their checks: for a lint
    failure, ruff on the changed Python files for a toolchain with the ruff gates; for a snapshot
    failure, the snapshot update of the tests whose snapshot differs, then the tests again; for a
    lint, a docs or a snapshot failure, the documents for a toolchain with the docs step, since a
    changed command or tool changes its snapshot and its documents (#6116); and for a lockfile
    failure, the lock file."""
    fixes: list[tuple[str, ...]] = []
    checks: list[tuple[str, ...]] = []
    if causes.lint and preset.step_gates == _RUFF_GATES and files:
        fixes += [
            (BIN_UV, "run", BIN_RUFF, "check", "--fix", "--", *files),
            (BIN_UV, "run", BIN_RUFF, "format", "--", *files),
        ]
        checks += [
            (BIN_UV, "run", BIN_RUFF, "check", "--", *files),
            (BIN_UV, "run", BIN_RUFF, "format", "--check", "--", *files),
        ]
    if causes.snapshots and preset.snapshot_update is not None:
        fixes.append(_with_tests(preset.snapshot_update, causes.snapshots))
        if preset.test_command is not None:
            checks.append(_with_tests(preset.test_command, causes.snapshots))
    if (causes.lint or causes.docs or causes.snapshots) and preset.docs_step:
        fixes.append((BIN_UV, "run", BIN_DEVOPS, "docs", "generate"))
        if preset.docs_verification:
            checks.append(preset.docs_verification)
    if causes.lock and (path / _LOCK_FILE).is_file():
        fixes.append((BIN_UV, "lock"))
        checks.append((BIN_UV, "lock", "--check"))
    return Tier1Commands(tuple(fixes), tuple(checks))


def _exit_status(path: Path, argv: Sequence[str], limit: int) -> int | None:
    """The exit status of `argv` in `path`, or None when it ran out of time."""
    try:
        return run_subprocess(
            list(argv), cwd=path, check=False, quiet=True, timeout=limit
        ).returncode
    except subprocess.TimeoutExpired:
        return None


def tier1_fix(path: Path, item: int, check: str, log: str) -> Fixed:
    """Tier 1, with no model request: run the fixers of a lint, a docs or a lockfile failure, commit
    the tracked files that they changed, and run their checks again. A fixer that exits non-zero,
    as `ruff check --fix` does when an error stays, does not stop the others. Done when the commit
    exists and every check passes; a commit whose check still fails stays for the model fix."""
    causes = tier1_causes(check, log)
    if not causes.found:
        return Fixed(
            done=False, reason="Tier 1 fixes only a lint, a docs, a lockfile or a snapshot failure"
        )
    base = _base(path)
    preset = resolve_profile(path, base).preset
    commands = tier1_commands(path, preset, _changed_python_files(path, base), causes)
    limit = load_settings().roadmap.implement.command_timeout_seconds
    for argv in commands.fixes:
        status = _exit_status(path, argv, limit)
        if status != 0:
            logger.info("fix-checks tier 1: %s exited %s", shlex.join(argv[:5]), status)
    git(path, "add", "-u", operation=_OPERATION)
    staged = git(path, "diff", "--cached", "--name-only", "-z", operation=_OPERATION)
    written = tuple(name for name in staged.split("\0") if name)
    if not written:
        return Fixed(done=False, reason="The fixers of tier 1 changed no file")
    message = f"style: apply the fixers of tier 1 for check {check} (#{item})"
    git(path, "commit", "-q", "-m", message, operation=_OPERATION)
    for argv in commands.checks:
        if _exit_status(path, argv, limit) != 0:
            return Fixed(
                done=False, reason=f"`{shlex.join(argv[:5])}` fails after tier 1", files=written
            )
    return Fixed(done=True, files=written)


def model_fix(store: ItemReader) -> ModelFixer:
    """Tier 2: the fix step of the implement job on the model of the task `fix_checks`, with no
    ladder, so a model trial moves this job alone (#5903). The step gets the hooks and the
    recorded tests of the default branch, as the implement job reads them, and the cap
    `roadmap.fix_checks.token_budget`. It may also change the files `extra` outside the plan,
    whose failure the change of the branch causes (#6116)."""

    def fix(path: Path, item: int, check: str, log: str, extra: tuple[str, ...]) -> Fixed:
        base = _base(path)
        hooks = trusted_config(path, base)
        if hooks is not None and (failure := install_hook_environments(path, hooks)) is not None:
            return Fixed(done=False, reason=failure)
        try:
            recorded = merged_recorded_tests(path, base, item, operation=_OPERATION)
        except PlanReadError as error:
            reason = MESSAGES.roadmap.plan_check_read.format(path=error.path, reason=error.reason)
            return Fixed(done=False, reason=reason)
        settings = load_settings()
        cap = TokenCap(setting=_CAP_SETTING, value=settings.roadmap.fix_checks.token_budget)
        try:
            outcome = run_fix_step(
                store,
                item=item,
                fix=FixRequest(check=check, log=log, extra_paths=extra),
                source=path,
                window=settings.ai.for_task(_TASK).context_window,
                model=get_task_model(_TASK),
                hooks=hooks,
                preset=resolve_profile(path, base).preset,
                ladder=(),
                recorded_tests=recorded,
                token_cap=cap,
            )
        except RoadmapImplementError as exc:
            return Fixed(done=False, reason=str(exc))
        if outcome.status is StepStatus.DONE:
            return Fixed(done=True)
        return Fixed(done=False, reason=outcome.reason)

    return fix


def job_repair(store: ItemReader, repo: str, *, source: Path | None = None) -> Repair:
    """The repair of a runner Job for `repo`, in the clone `source`, or in the clone `model-clone`,
    which is made or updated only when a round opens the checkout."""

    def checkout(status: PullStatus, item: int) -> AbstractContextManager[PullCheckout]:
        return pull_checkout(repo, status, item, source)

    return Repair(checkout=checkout, tier1=tier1_fix, model=model_fix(store))
