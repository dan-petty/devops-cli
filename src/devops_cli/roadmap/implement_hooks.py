"""The hooks of the repository, run by the implement job as the hooks of a person's commit and push
(#3043).

`pre-commit` reads the single definition, `.pre-commit-config.yaml`. The job starts it as its own
child with `pre-commit run --hook-stage <stage>`, and installs no git hook. A hook installed in
the clone would run inside `git commit` and `git push`, and the process runner gives every `git`
child the GitHub token of the session. The agent can edit the configuration, so a hook of its own
would hold the token. The child here is `uv`, which gets no token. The Job runs the stage itself
before the commit and before the push, so a failed hook reaches the agent while a repair round
is left.

The agent can edit the configuration too, and an edit such as `repos: []` would make every hook
pass. So no run reads the file of the checkout. `trusted_config` writes the configuration of the
default branch to the cache directory, and each run gets it with `--config`.

The environments of the two remote hook repositories are fetched at run time into the cache
directory of the data directory, which is on the home volume of the Job. The perimeter of the
Job admits public HTTPS.
"""

from __future__ import annotations

import subprocess
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path

import yaml

from devops_cli.config.commands import BIN_PRE_COMMIT, BIN_UV
from devops_cli.config.constants import (
    CONST_PRE_COMMIT_COMMIT_STAGE,
    CONST_PRE_COMMIT_CONFIG_FILENAME,
    CONST_PRE_COMMIT_HOME_DIR,
    CONST_PRE_COMMIT_HOME_ENV,
    CONST_PRE_COMMIT_TRUSTED_CONFIG_FILE,
    CONST_ROADMAP_IMPLEMENT_COMMAND_TIMEOUT_SECONDS,
    CONST_ROADMAP_IMPLEMENT_HOOK_OUTPUT_CHARS,
)
from devops_cli.config.settings import load_settings
from devops_cli.core.process import run_subprocess
from devops_cli.core.repo import resolve_data_path
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.clone_git import git
from devops_cli.roadmap.runner_tools import hooks_without_programs
from devops_cli.security.sanitizer import mask_secrets

_OPERATION = "roadmap.implement.hooks"
# pre-commit exits 1 when a hook fails or changes a file. Any other code is an error of the tool.
_HOOKS_FAILED = 1
# The exit code of a run that ran out of time, as the `timeout` program reports it. No agent can
# repair it, so it is no `_HOOKS_FAILED`.
_TIMED_OUT = 124


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


def _cache_dir() -> Path:
    """The cache directory of the data directory."""
    return resolve_data_path(load_settings().data.cache_dir)


def _without_hooks(text: str, skipped: Collection[str]) -> str:
    """`text`, a hook configuration, without the hooks `skipped`, and without a repository that
    keeps no hook. The text is the same when it holds none of them."""
    config = yaml.safe_load(text) if skipped else None
    if not isinstance(config, dict) or not isinstance(config.get("repos"), list):
        return text
    repos = config["repos"]
    kept = []
    changed = False
    for repo in repos:
        hooks = repo.get("hooks") if isinstance(repo, dict) else None
        if not isinstance(hooks, list):
            kept.append(repo)
            continue
        left = [
            hook for hook in hooks if not (isinstance(hook, dict) and hook.get("id") in skipped)
        ]
        changed = changed or len(left) != len(hooks)
        if left:
            kept.append({**repo, "hooks": left})
    if not changed:
        return text
    return yaml.safe_dump({**config, "repos": kept}, sort_keys=False).rstrip("\n")


def trusted_config(source: Path, ref: str) -> Path | None:
    """The configuration of the hooks as commit `ref` holds it, written to the cache directory:
    the file that every hook run gets with `--config`. None when `ref` holds no configuration, as
    a repository with no hook has none to run. The commit decides, not the files of the checkout,
    so an agent that removes or edits the file does not skip a hook. The one hooks it leaves out
    are those that run a program the runner image does not hold (`HOOK_PROGRAMS`): the checks of
    the pull request run them. Raises `GitOperationError` when git cannot read `ref`."""
    name = CONST_PRE_COMMIT_CONFIG_FILENAME
    listed = git(source, "ls-tree", "--name-only", ref, "--", name, operation=_OPERATION)
    if not listed:
        return None
    text = git(source, "show", f"{ref}:{name}", operation=_OPERATION)
    target = _cache_dir() / CONST_PRE_COMMIT_TRUSTED_CONFIG_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(f"{_without_hooks(text, hooks_without_programs())}\n", encoding="utf-8")
    return target


def hook_environment() -> dict[str, str]:
    """The variables of a `pre-commit` child: the directory of the hook environments, in the cache
    directory of the data directory."""
    return {CONST_PRE_COMMIT_HOME_ENV: str(_cache_dir() / CONST_PRE_COMMIT_HOME_DIR)}


def output_text(stdout: str | None, stderr: str | None) -> str:
    """What a child printed, masked, with its last characters."""
    text = mask_secrets(f"{stdout or ''}{stderr or ''}").strip()
    return text[-CONST_ROADMAP_IMPLEMENT_HOOK_OUTPUT_CHARS:]


def pre_commit_command(config: Path, *args: str) -> list[str]:
    """The command line of `pre-commit <args>` with the configuration `config`, started with `uv`
    from the environment of the checkout. The child is no `git` or `gh` client, so it holds no
    token."""
    return [BIN_UV, "run", BIN_PRE_COMMIT, *args, "--config", str(config)]


def _pre_commit(source: Path, config: Path, *args: str) -> HookRun:
    """Run `pre-commit <args>` in the checkout. A run that runs out of time is a failure that no
    repair round can fix."""
    command = pre_commit_command(config, *args)
    try:
        done = run_subprocess(
            command,
            cwd=source,
            env=hook_environment(),
            quiet=True,
            timeout=CONST_ROADMAP_IMPLEMENT_COMMAND_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        text = MESSAGES.roadmap.implement_stop_command_timeout.format(
            command=" ".join(command), seconds=CONST_ROADMAP_IMPLEMENT_COMMAND_TIMEOUT_SECONDS
        )
        return HookRun(_TIMED_OUT, text)
    return HookRun(done.returncode, output_text(done.stdout, done.stderr))


def stage_arguments(stage: str, *options: str) -> tuple[str, ...]:
    """The arguments of `pre-commit` that run the hooks of `stage`, with `options` such as
    `--from-ref` and `--to-ref`."""
    return ("run", "--hook-stage", stage, *options)


def stage_run(source: Path, config: Path, stage: str, *options: str) -> HookRun:
    """One run of the hooks of `stage` with the configuration `config`, and `options` such as
    `--from-ref` and `--to-ref`. With no option, the run reads the staged changes of the checkout."""
    return _pre_commit(source, config, *stage_arguments(stage, *options))


def commit_stage(source: Path, config: Path) -> HookRun | None:
    """Run the `pre-commit` stage over the staged changes. A hook that fixes a file makes the stage
    exit 1: the files that the hooks changed are staged, and the stage runs once more, as a person
    adds the files and commits again. None when the stage passes, else the failing run."""
    run = stage_run(source, config, CONST_PRE_COMMIT_COMMIT_STAGE)
    if run.returncode == 0:
        return None
    listed = git(source, "diff", "--name-only", "-z", operation=_OPERATION)
    changed = [name for name in listed.split("\0") if name]
    if not run.repairable or not changed:
        return run
    git(source, "add", "--", *changed, operation=_OPERATION)
    again = stage_run(source, config, CONST_PRE_COMMIT_COMMIT_STAGE)
    return None if again.returncode == 0 else again


def install_hook_environments(source: Path, config: Path) -> str | None:
    """Fetch and build the hook environments of `config` with `pre-commit install-hooks`. None when
    it exits 0, else the message that says the install failed, with the output."""
    run = _pre_commit(source, config, "install-hooks")
    if run.returncode == 0:
        return None
    return MESSAGES.roadmap.implement_stop_hooks_install.format(output=run.output)
