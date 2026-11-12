# Design

## Decisions

- The hook is one inline command, not a script file. `devops devcontainer init` writes the same settings into other repositories, which do not have a script of this repository. The command is POSIX shell, so bash and dash run it the same.
- The hook checks `CLAUDE_CODE_REMOTE`, as the Claude Code document shows. The devcontainer already installs the hooks at each start, so a local session does nothing.
- The hook sends the output of `pre-commit install` to stderr. Claude Code adds plain stdout of a SessionStart hook to the context, and the install lines are of no use to the model.
- The hook keeps the default limit of 600 s of a `command` hook. The first start of a cloud session syncs the environment of the project, which the hooks need anyway, because they run `uv run devops ci`.
- The Copilot step adds `--install-hooks`. The setup step runs outside the firewall of the agent, so it can clone the hook repositories from github.com and install them from PyPI. The agent's own commits then need no download.
- `uv run pre-commit install` is the same command that `devops devcontainer post-start` runs.

## Rejected alternatives

- A setup script of the cloud environment: it is set in the claude.ai environment dialog, not in the repository, so it does not reach every session of the repository.
- `uvx pre-commit install`: the installed hook names the Python of a temporary tool environment, which uv can delete. The project `.venv` stays.
- A hook with `async: true`: a commit could start before the install ends.
