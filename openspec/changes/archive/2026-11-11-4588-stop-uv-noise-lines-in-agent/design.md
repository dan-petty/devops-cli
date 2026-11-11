# Design

## Decisions

- Set the two values in the `env` of `.claude/settings.json`. The file is in every worktree, and Claude Code reads it for each session, also for a `claude` that starts from a VS Code terminal with an active environment.
- Set `VIRTUAL_ENV` to an empty value. Claude Code cannot remove a variable that its parent sets, and uv reads an empty value as unset.
- Set `UV_COMPILE_BYTECODE` to `0` only for Claude Code. The image keeps the value `1` for the other shells and for the runner pods.

## Rejected alternatives

- `python.terminal.activateEnvironment: false` in `.devcontainer/devcontainer.json`: it acts only on VS Code terminals, and the agent shells do not start from them.
- `claudeCode.usePythonEnvironment: false` in `.devcontainer/devcontainer.json`: it acts only after a rebuild of the container, and only for the VS Code extension. A `claude` that starts from an activated terminal keeps `VIRTUAL_ENV`.
- `uv run -q`: it also hides the lines of an editable reinstall, which tell an agent that the venv changed.
- `UV_COMPILE_BYTECODE=0` in the root `Dockerfile`: the runner pods have a read-only root file system, so Python cannot write the `.pyc` files at run time.
