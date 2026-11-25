# Proposal: #6486

## Why
`devops devcontainer init` exposes two options that have no effect on its output:
- `--published` / `-p`: `init` ignores its value and computes `is_published` solely from `image`.
- `--python`: `init` forwards `python_version` into `render_json_template`, which `devcontainer.json.j2` no longer reads after #6412.

Advertising unused options in CLI help and docs misleads callers into expecting behavior changes that do not happen.

## What Changes
- Remove `--published` (`-p`) and `--python` from `devops devcontainer init` in `src/devops_cli/commands/devcontainer.py`.
- Stop passing `python_version` in `init`'s `render_json_template("devcontainer.json.j2", ...)` call while keeping `image` and `published`.
- Remove the unused `DevcontainerCommandHelp.published` field from `src/devops_cli/lang/en/help.py` while keeping `--python` on `devops devcontainer update`.
- Remove `--published` from `docs/DEVCONTAINER_USAGE.md` and regenerate CLI reference docs via `uv run devops docs generate`.
- Update `tests/commands/test_devcontainer.py` to verify `init --help`, nonzero rejection of `--published`/`--python`, `render_json_template` context keys, and `update --python`.

## Capabilities

### New Capabilities
- `devcontainer-init-options`: Enforce that `devops devcontainer init` accepts only active options, rejects removed `--published`/`--python`, omits `python_version` from its render call, and keeps docs and tests aligned.

## Impact
- Callers passing `--published`, `-p`, or `--python` to `devops devcontainer init` receive a standard Click/Typer nonzero usage error.
- `devops devcontainer update --python` keeps working as before.

## Feasibility
- Confirmed on `origin/main`: `src/devops_cli/commands/devcontainer.py:100-179` defines `--python` and `--published` on `init` and passes unused `python_version`, `src/devops_cli/templates/devcontainer.json.j2` never references `python_version`, and `docs/DEVCONTAINER_USAGE.md:69` still shows `init --published`.

## Existing Tool Considered
- No external tool or library exists for pruning dead CLI options in this project's Typer commands. Estimated custom cost: ~35 lines edited across command, help catalog, docs, and tests (~10k tokens, ~15 minutes).
