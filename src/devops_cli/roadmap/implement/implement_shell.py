"""The stock harness shell of an implement step (#6527)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Final

from platformdirs import user_cache_dir
from pydantic_ai import RunContext
from pydantic_ai.capabilities import Hooks, ValidatedToolArgs
from pydantic_ai.messages import ToolCallPart
from pydantic_ai.tools import ToolDefinition
from pydantic_ai_harness.shell import Shell

from devops_cli.config.settings import load_settings
from devops_cli.roadmap.implement.implement_broker import live_broker
from devops_cli.roadmap.runner_tools import checkout_environment

# The tool of the harness that runs a command of the agent. It waits until the command ends, up to
# the command limit of the step, and returns the output (#4493). The persistent tool `shell`
# returned after 270 s with a PID and a log, and the agent read the log again and again.
IMPLEMENT_SHELL_TOOL: Final[str] = "run_command"

_PASSED_VARIABLES: Final[tuple[str, ...]] = ("UV_PYTHON", "PYTEST_XDIST_AUTO_NUM_WORKERS")


def shell_environment(home: Path, source: Path) -> dict[str, str]:
    """The variables a shell command gets on top of the workspace's own: a scratch `home` in place
    of the user's, so that no git configuration, credential helper or key of the user reaches the
    agent, no system git configuration, no prompt for a password, the cache of `uv` where the
    user keeps it, so that `uv run` finds its packages, and a PATH with the Node tools and the venv
    of the checkout `source` first, as the bootstrap of the Job built them: the runner image holds
    no dev dependency (#6517). The variables in `_PASSED_VARIABLES` go on
    when the process has them. `UV_PYTHON`: the runner image sets it, as it forbids a Python
    download and `uv run` finds no interpreter without it. `PYTEST_XDIST_AUTO_NUM_WORKERS`: the
    pod of the runner sets it to its CPU limit, as `pytest-xdist` counts the CPUs of the node and
    a test run started one worker for each of them (#2806). `AI_AGENT` names the agent tool, so a
    usage error of a devops command that the agent runs records the caller agent (#4839). A live
    broker of the step adds its address and the token of the step, which are no variables of the
    job and hold no AI key (#3820)."""
    env = {
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "UV_CACHE_DIR": os.environ.get("UV_CACHE_DIR") or user_cache_dir("uv"),
        "AI_AGENT": "devops-implement",
        **checkout_environment(source),
    }
    env.update({name: os.environ[name] for name in _PASSED_VARIABLES if os.environ.get(name)})
    broker = live_broker()
    if broker is not None and broker.token is not None:
        env["DEVOPS_CLI_BROKER_URL"] = broker.url
        env["DEVOPS_CLI_BROKER_TOKEN"] = broker.token
    return env


def step_shell(home: Path, source: Path) -> Shell:
    """The stock `Shell` of an implement step: `run_command` with
    `roadmap.implement.command_timeout_seconds`, the scratch `shell_environment`, and no allowed or
    denied command."""
    command_timeout = load_settings().roadmap.implement.command_timeout_seconds
    return Shell(
        tools=[IMPLEMENT_SHELL_TOOL],
        default_timeout=command_timeout,
        allowed_commands=[],
        denied_commands=[],
        denied_operators=[],
        allow_interactive=False,
        env=shell_environment(home, source),
    )


def shell_timeout_hooks(timeout: float) -> Hooks[None]:
    """Force every `run_command` call to wait `timeout` seconds, overriding any wait passed by
    the model (#4493, #6527)."""

    async def set_timeout(
        _ctx: RunContext[Any],
        /,
        *,
        call: ToolCallPart,
        tool_def: ToolDefinition,
        args: ValidatedToolArgs,
    ) -> ValidatedToolArgs:
        if call.tool_name == IMPLEMENT_SHELL_TOOL:
            return {**args, "timeout_seconds": timeout}
        return args

    return Hooks(before_tool_execute=set_timeout)
