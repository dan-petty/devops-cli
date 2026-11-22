"""The repair that the step `fix-checks` uses in a runner Job (#5971).

The command `devops roadmap step fix-checks --confirm` gives the step `job_repair`:

- The checkout (`prepare`): a plain clone of the repository on GitHub in the work folder of the
  run, on the head branch of the pull request (`clone_branch`, #3702), with the tip of the default
  branch that the clone read. The App must have written every commit of the branch past main, and
  the branch must be at the judged head. The clone holds no credential: git gets the token of
  each call that reaches `origin` from its environment. The run folder of `--phase all` is in the
  data folder and goes when the round ends. On the runner Job, the run folder is `/run/roadmap`
  (volume `run`), and the clone is in its `work/` (#3700).
- The rebase (`agent`, #6639): a branch that is behind the default branch is rebased onto the
  tip that `prepare` read, as implement rebases it (`rebase_onto`). A rebase that skipped the
  archive commit of the item archives the change again, in a commit of its own. A stop that no
  rule settles aborts the rebase and stops the round with the conflicted files.
- The publish (`publish`): the patches of the checkout (`write_patch`), each that is not empty
  applied as one commit of the bot on the base, the judged head or the `onto` that `prepare`
  recorded for a rebased branch, and pushed to the head branch with a lease on the judged head
  (`publish_patch`), so it never overwrites a push of another writer. `publish` reads the workflow files that the merged plan of
  the item names on the default branch of GitHub (`merged_workflows`).
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
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from devops_cli.ai.client.factory import get_task_model
from devops_cli.config.commands import BIN_DEVOPS, BIN_RUFF, BIN_UV
from devops_cli.config.constants import (
    CONST_GITHUB_CLONE_URL,
    CONST_GITHUB_WORKFLOWS_DIR,
    CONST_OPENSPEC_CHANGES_DIR,
    CONST_ROADMAP_FIX_CHECKS_RUNS_DIR,
)
from devops_cli.config.settings import load_settings
from devops_cli.core.process import run_subprocess
from devops_cli.core.repo import resolve_data_path
from devops_cli.exceptions import DevOpsCLIError, ToolExecutionError
from devops_cli.exceptions.roadmap import RoadmapImplementError
from devops_cli.github.client import PullStatus
from devops_cli.github.session import get_github_session
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.clone_git import default_branch, git
from devops_cli.roadmap.implement.implement_hooks import install_hook_environments, trusted_config
from devops_cli.roadmap.implement.implement_limits import TokenCap
from devops_cli.roadmap.implement.implement_step import (
    FixRequest,
    ItemReader,
    StepStatus,
    run_fix_step,
)
from devops_cli.roadmap.implement.implement_strays import plan_paths
from devops_cli.roadmap.phases.checkout import clone_branch
from devops_cli.roadmap.phases.patch import write_patch
from devops_cli.roadmap.phases.publish import NewTree, Published, PublishTarget, publish_patch
from devops_cli.roadmap.phases.rebase import (
    RebaseEnd,
    archive_change,
    commit_changed,
    rebase_onto,
    unmerged,
)
from devops_cli.roadmap.plan_read import PlanReadError, merged_recorded_tests
from devops_cli.roadmap.project_profile import resolve_profile
from devops_cli.roadmap.runner_tools import bootstrap_checkout, checkout_environment
from devops_cli.roadmap.step_files import parse_task_groups
from devops_cli.roadmap.steps.fix_checks import (
    Fixed,
    ModelFixer,
    PullCheckout,
    Repair,
    Tier1Causes,
    tier1_causes,
)
from devops_cli.roadmap.toolchains import ToolchainPreset
from devops_cli.security.sanitizer import mask_secrets

logger = logging.getLogger(__name__)

# The operation that a failed git call of the step names.
_OPERATION: Final[str] = "roadmap.fix_checks"
# The task of the model fix, and the setting of its cap (#5971).
_TASK: Final[str] = "fix_checks"
_CAP_SETTING: Final[str] = "roadmap.fix_checks.token_budget"
# The toolchain gates that run ruff, as the implement step reads them.
_RUFF_GATES: Final[str] = "ruff-mypy"
_LOCK_FILE: Final[str] = "uv.lock"


def open_checkout(repo: str, status: PullStatus, item: int, work: Path) -> PullCheckout:
    """The clone of `repo` in the work folder `work` on the head branch of the pull request of
    `status`, the branch of `item` (#3702). The switch refuses a branch with a commit past main that
    the App did not write, and the branch must be at the judged head. It runs git calls only, and
    no program of the branch."""
    clone = clone_branch(
        work, url=CONST_GITHUB_CLONE_URL.format(repo=repo), issue=item, branch=status.head_ref
    )
    if clone.lease != status.head_sha:
        raise RoadmapImplementError(
            f"The head branch `{clone.branch}` is at {clone.lease[:12]}, not at the judged head "
            f"{status.head_sha[:12]}."
        )
    (clone.path / ".data" / "agent" / "scratch").mkdir(parents=True, exist_ok=True)
    return PullCheckout(clone.path, clone.base)


def merged_workflows(repo: str, ref: str, item: int) -> tuple[str, ...]:
    """The workflow files that the merged plan of `item` names on the branch `ref` of GitHub, read
    by `publish` with the App key, where the agent cannot change them (#2695, #6601). A branch
    with no one active change of the item, or a plan that GitHub cannot give, names none, so the
    patch writes no workflow file."""
    client = get_github_session().client
    names = [
        name
        for name in client.folder_names_at(repo, CONST_OPENSPEC_CHANGES_DIR, ref)
        if name.startswith(f"{item}-")
    ]
    if len(names) != 1:
        return ()
    text = client.get_file_at(repo, f"{CONST_OPENSPEC_CHANGES_DIR}/{names[0]}/tasks.md", ref)
    if not text:
        return ()
    return tuple(
        sorted(
            name
            for name in plan_paths(parse_task_groups(text))
            if name.startswith(CONST_GITHUB_WORKFLOWS_DIR)
        )
    )


def _runs() -> Path:
    """The folder of the run folders of `--phase all` only, in the data folder (#6601). On the
    runner Job, the run folder is `/run/roadmap` (volume `run`), and the clone is in its `work/`
    (#3700)."""
    folder = resolve_data_path(load_settings().data.dir) / CONST_ROADMAP_FIX_CHECKS_RUNS_DIR
    folder.mkdir(parents=True, exist_ok=True)
    return folder


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
    """The exit status of `argv` in `path`, with the tools of the checkout first on PATH, or None
    when it ran out of time."""
    try:
        return run_subprocess(
            list(argv),
            cwd=path,
            env=checkout_environment(path),
            check=False,
            quiet=True,
            timeout=limit,
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


def _conflict_reason(ended: RebaseEnd, files: Sequence[str]) -> str:
    """The reason of a rebase that a stop ended: the error of git when it refused to go on from
    a settled stop (`stuck`), else the conflicted files that no rule settles."""
    if ended.stuck:
        return f"Conflict: {mask_secrets(str(ended.error))}"
    named = ", ".join(f"`{mask_secrets(name)}`" for name in files)
    return f"Conflict: the rebase onto main stops on {named or 'no file'}, which no rule settles"


def rebase_branch(path: Path, onto: str, item: int) -> Fixed:
    """Rebase the checkout `path` onto `onto`, the tip of the default branch that `prepare` read,
    and settle each stop as implement does (`rebase_onto`, #6639). Done when the branch sits on
    `onto`; else not done, with the reason: the rebase is aborted, and a conflict that no rule
    settles names each conflicted file."""
    preset = resolve_profile(path, onto).preset
    limit = load_settings().roadmap.implement.command_timeout_seconds

    def generate(argv: Sequence[str]) -> None:
        if _exit_status(path, argv, limit) != 0:
            raise RoadmapImplementError(f"`{shlex.join(argv[:5])}` failed after the rebase")

    def abort() -> list[str]:
        files = unmerged(path, operation=_OPERATION)
        git(path, "rebase", "--abort", operation=_OPERATION)
        return files

    try:
        ended = rebase_onto(path, onto, item, generate, docs=preset.docs_step, operation=_OPERATION)
    except DevOpsCLIError as exc:
        abort()
        return Fixed(done=False, reason=f"The rebase onto main stopped: {mask_secrets(str(exc))}")
    if not ended.started:
        return Fixed(done=False, reason="git refused to start the rebase onto main")
    if ended.error is not None:
        return Fixed(done=False, reason=_conflict_reason(ended, abort()))
    if ended.skipped:

        def commit(message: str) -> None:
            commit_changed(path, message, operation=_OPERATION)

        try:
            archive_change(path, item, preset, generate, commit, docs=preset.docs_step)
        except DevOpsCLIError as exc:
            output = mask_secrets(str(exc))
            return Fixed(done=False, reason=f"The change was not archived again: {output}")
    return Fixed(done=True)


def model_fix(store: ItemReader) -> ModelFixer:
    """Tier 2: the fix step of the implement job on the model of the task `fix_checks`, with no
    ladder, so a model trial moves this job alone (#5903). The step gets the hooks and the
    recorded tests of the default branch, as the implement job reads them, and the cap
    `roadmap.fix_checks.token_budget`. It may also change the files `extra` outside the plan,
    whose failure the change of the branch causes (#6116). Before the step it builds the coder
    environment of the worktree (#6517). The branch exists, so the bootstrap installs its
    `uv.lock` as it is and writes no lock, and the install of the hook environments locks nothing
    (`uv run --frozen`). So the step finds a clean worktree, and locks a stale lock again in its
    shell (#6557). Tier 1 runs only `uv run` and `uv lock`, which build what they need, so it
    needs no bootstrap."""

    def fix(path: Path, item: int, check: str, log: str, extra: tuple[str, ...]) -> Fixed:
        try:
            bootstrap_checkout(path, locked=False)
        except ToolExecutionError as exc:
            return Fixed(done=False, reason=str(exc))
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


def _bot() -> tuple[str, str]:
    """The name and the email of the identity of the session, the bot of the App in a runner."""
    session = get_github_session()
    return session.login, session.commit_email


def job_repair(repo: str) -> Repair:
    """The repair of a runner Job for `repo`, by phase (#6601): the clone in the work folder; tier
    1; the model fix, which reads the item that `prepare` gave it; the patches of the checkout; and
    the publish of each patch that is not empty as one commit of the bot on the base. `publish`
    reads the bot and the workflow files of the plan itself, and pushes to the repository on
    GitHub."""
    scratch = _runs()

    def checkout(status: PullStatus, item: int, work: Path) -> PullCheckout:
        return open_checkout(repo, status, item, work)

    def publish(
        target: PublishTarget,
        patches: Sequence[tuple[bytes, str]],
        before_push: Callable[[NewTree], None],
    ) -> Published | None:
        # The new repository goes to the temporary folder of `publish` (#3700, #6743).
        return publish_patch(target, patches, before_push=before_push)

    return Repair(
        checkout=checkout,
        tier1=tier1_fix,
        model=model_fix,
        rebase=rebase_branch,
        patch=write_patch,
        publish=publish,
        author=_bot,
        workflows=merged_workflows,
        scratch=scratch,
    )
