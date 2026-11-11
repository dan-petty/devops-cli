# Proposal: #4588

## Why

Issue #4588: each `uv run` in a Claude Code shell writes noise lines. The context audit of 2026-11 counts about 20.6M tokens a week for them.

- In a git worktree, uv writes `warning: VIRTUAL_ENV=/workspaces/devops-cli/.venv does not match the project environment path .venv and will be ignored; use --active to target the active environment instead`. The advice is harmful: `--active` points the editable install of the main `.venv` at the worktree.
- Each `uv run` writes `Bytecode compiled 19212 files in <n>ms`, because the devcontainer image sets `UV_COMPILE_BYTECODE=1` (`.devcontainer/Dockerfile`).

## What Changes

- The `env` of `.claude/settings.json` and of its template `src/devops_cli/templates/claude_settings.json.j2` sets `VIRTUAL_ENV` to `""` and `UV_COMPILE_BYTECODE` to `"0"`. The other keys of the file stay.
- A new test in `tests/commands/test_devcontainer.py` holds the two values in the settings that `devops devcontainer init` writes. The test that compares the scaffold with the committed file holds the committed file.
- `CONTRIBUTING.md` (Shell notes for agents, item 3) describes the two values and tells agents not to use `--active`.
- Not changed: `UV_COMPILE_BYTECODE=1` in the root `Dockerfile`, because the runner pods have a read-only root file system and need the compiled bytecode in the image; the `.devcontainer/Dockerfile`, `.devcontainer/devcontainer.json`, and `uv run -q`, which also hides the lines of an editable reinstall.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `devcontainer-agent-config`: a new requirement, "Claude Code sessions run uv with no environment warning and no bytecode line".

## Impact

- `.claude/settings.json`, `src/devops_cli/templates/claude_settings.json.j2`, `tests/commands/test_devcontainer.py`, `CONTRIBUTING.md`.
- A Claude Code session reads the new values when it starts. A running session keeps its old environment.
- Python writes the `.pyc` file of a module the first time it imports the module, not at install time. The `devops ci` gate is not changed: it runs `uv sync --compile-bytecode`, and the flag has priority over the variable (`tests/commands/test_ci.py`).

## Feasibility

Read on 2026-11-11.

- The audit names `python.terminal.activateEnvironment: true` in `.devcontainer/devcontainer.json` as the cause. It is not the cause for agent shells. `/proc/<pid>/environ` of the `claude` process holds `VIRTUAL_ENV=/workspaces/devops-cli/.venv`, and the extension host that starts it does not. The Kilo process, which the same extension host starts, has no `VIRTUAL_ENV`. The VS Code setting acts only on VS Code terminals.
- The source is the setting `claudeCode.usePythonEnvironment` of the Claude Code VS Code extension (default `true`, `package.json` of extension 2.1.322). Its `extension.js` asks the Python extension for the active environment and starts `claude` with `VIRTUAL_ENV` set to its `sys.prefix` and its `bin` first on `PATH`.
- uv reads an empty `VIRTUAL_ENV` as unset. In a scratch project with uv 0.13.6, `VIRTUAL_ENV= uv run python -c 'import sys;print(sys.prefix)'` writes no warning and prints the project `.venv`. With `UV_COMPILE_BYTECODE=0`, uv writes no `Bytecode compiled` line.
- Claude Code puts the `env` of the project settings into the environment of its Bash tool. A headless `claude -p` session in the worktree, started from a shell with `VIRTUAL_ENV=/workspaces/devops-cli/.venv` and `UV_COMPILE_BYTECODE=1`, ran `printenv VIRTUAL_ENV UV_COMPILE_BYTECODE; uv run python -c 'import sys;print(sys.prefix)'` and got an empty line, `0`, and the worktree `.venv` path, with no warning and no bytecode line.

## Existing Tool Considered

The `env` key of the Claude Code settings and the uv variables `VIRTUAL_ENV` and `UV_COMPILE_BYTECODE` do the work. No code is built.
