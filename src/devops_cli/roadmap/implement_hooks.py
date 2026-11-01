"""The hooks of the repository, run by the implement job as the hooks of a person's commit and push
(#3043).

`pre-commit` reads the single definition, `.pre-commit-config.yaml`. The job starts it as its own
child with `pre-commit run --hook-stage <stage>`, and installs no git hook. A hook installed in
the clone would run inside `git commit` and `git push`, and the process runner gives every `git`
child the GitHub token of the session. The agent can edit the configuration, so a hook of its own
would hold the token. The child here is `uv`, which gets no token. The Job runs the stage itself
before the commit and before the push, so a failed hook reaches the agent while a repair round
is left.

The environments of the two remote hook repositories are fetched at run time into the cache
directory of the data directory, which is on the home volume of the Job. The perimeter of the
Job admits public HTTPS.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from devops_cli.config.commands import BIN_GIT, BIN_PRE_COMMIT, BIN_UV
from devops_cli.config.constants import (
    CONST_PRE_COMMIT_COMMIT_STAGE,
    CONST_PRE_COMMIT_CONFIG_FILENAME,
    CONST_PRE_COMMIT_HOME_DIR,
    CONST_PRE_COMMIT_HOME_ENV,
    CONST_ROADMAP_IMPLEMENT_COMMAND_TIMEOUT_SECONDS,
    CONST_ROADMAP_IMPLEMENT_HOOK_OUTPUT_CHARS,
)
from devops_cli.config.settings import load_settings
from devops_cli.core.process import run_subprocess
from devops_cli.core.repo import resolve_data_path
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.clone_git import git
from devops_cli.security.sanitizer import mask_secrets

_OPERATION = "roadmap.implement.hooks"
# pre-commit exits 1 when a hook fails or changes a file. Any other code is an error of the tool.
_HOOKS_FAILED = 1


@dataclass(frozen=True)
class HookRun:
    """The end of one run of a hook stage: its exit code, and its output with secrets masked and
    cut to its last `CONST_ROADMAP_IMPLEMENT_HOOK_OUTPUT_CHARS` characters."""

    returncode: int
    output: str

    @property
    def repairable(self) -> bool:
        """Whether the agent can fix the failure: a hook failed, and the tool itself ran."""
        return self.returncode == _HOOKS_FAILED


def has_hooks(source: Path, ref: str = "HEAD") -> bool:
    """Whether the commit `ref` of the checkout holds the configuration of the hooks. The commit
    decides, not the files of the checkout, so an agent that removes the file does not skip the
    hooks. A repository with no configuration has no hook to run."""
    done = run_subprocess(
        [BIN_GIT, "cat-file", "-e", f"{ref}:{CONST_PRE_COMMIT_CONFIG_FILENAME}"],
        cwd=source,
        quiet=True,
        timeout=CONST_ROADMAP_IMPLEMENT_COMMAND_TIMEOUT_SECONDS,
    )
    return done.returncode == 0


def hook_environment() -> dict[str, str]:
    """The variables of a `pre-commit` child: the directory of the hook environments, in the cache
    directory of the data directory."""
    cache = resolve_data_path(load_settings().data.cache_dir)
    return {CONST_PRE_COMMIT_HOME_ENV: str(cache / CONST_PRE_COMMIT_HOME_DIR)}


def output_text(stdout: str | None, stderr: str | None) -> str:
    """What a child printed, masked, with its last characters."""
    text = mask_secrets(f"{stdout or ''}{stderr or ''}").strip()
    return text[-CONST_ROADMAP_IMPLEMENT_HOOK_OUTPUT_CHARS:]


def pre_commit_command(*args: str) -> list[str]:
    """The command line of `pre-commit <args>`, started with `uv` from the environment of the
    checkout. The child is no `git` or `gh` client, so it holds no token."""
    return [BIN_UV, "run", BIN_PRE_COMMIT, *args]


def _pre_commit(source: Path, *args: str) -> HookRun:
    """Run `pre-commit <args>` in the checkout."""
    done = run_subprocess(
        pre_commit_command(*args),
        cwd=source,
        env=hook_environment(),
        quiet=True,
        timeout=CONST_ROADMAP_IMPLEMENT_COMMAND_TIMEOUT_SECONDS,
    )
    return HookRun(done.returncode, output_text(done.stdout, done.stderr))


def stage_arguments(stage: str, *options: str) -> tuple[str, ...]:
    """The arguments of `pre-commit` that run the hooks of `stage`, with `options` such as
    `--from-ref` and `--to-ref`."""
    return ("run", "--hook-stage", stage, *options)


def stage_run(source: Path, stage: str, *options: str) -> HookRun:
    """One run of the hooks of `stage`, with `options` such as `--from-ref` and `--to-ref`. With no
    option, the run reads the staged changes of the checkout."""
    return _pre_commit(source, *stage_arguments(stage, *options))


def commit_stage(source: Path) -> HookRun | None:
    """Run the `pre-commit` stage over the staged changes. A hook that fixes a file makes the stage
    exit 1: the files that the hooks changed are staged, and the stage runs once more, as a person
    adds the files and commits again. None when the stage passes, else the failing run."""
    run = stage_run(source, CONST_PRE_COMMIT_COMMIT_STAGE)
    if run.returncode == 0:
        return None
    listed = git(source, "diff", "--name-only", "-z", operation=_OPERATION)
    changed = [name for name in listed.split("\0") if name]
    if not run.repairable or not changed:
        return run
    git(source, "add", "--", *changed, operation=_OPERATION)
    again = stage_run(source, CONST_PRE_COMMIT_COMMIT_STAGE)
    return None if again.returncode == 0 else again


def install_hook_environments(source: Path) -> str | None:
    """Fetch and build the hook environments with `pre-commit install-hooks`. None when it exits
    0, else the message that says the install failed, with the output."""
    run = _pre_commit(source, "install-hooks")
    if run.returncode == 0:
        return None
    return MESSAGES.roadmap.implement_stop_hooks_install.format(output=run.output)
