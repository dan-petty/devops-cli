# Design

## Decisions
- **Remove `--published`/`-p` and `--python` from `init` while preserving `update --python`**: Drop both unused Typer options from `init` in `src/devops_cli/commands/devcontainer.py`, keep `is_published = image is None`, and drop `python_version` from `render_json_template("devcontainer.json.j2", ...)` while keeping `image` and `published` so `devcontainer.json.j2` and template tests require no template break. [sources: src/devops_cli/commands/devcontainer.py:100-179, src/devops_cli/templates/devcontainer.json.j2:1-7]
- **Remove orphaned help field `HELP.devcontainer.published`**: Because only `init` referenced `HELP.devcontainer.published` while `update` still uses `HELP.devcontainer.python_version`, removing `published` from `DevcontainerCommandHelp` keeps the language catalog clean without affecting `update`. [sources: src/devops_cli/lang/en/help.py:1207-1209, src/devops_cli/commands/devcontainer.py:241]
- **Regenerate docs and update usage guide**: Remove `--published` from `docs/DEVCONTAINER_USAGE.md:69` and regenerate `docs/commands/devcontainer.md` via `devops docs generate`. [sources: docs/DEVCONTAINER_USAGE.md:69]

## Rejected alternatives
- **Keeping `--published` as a hidden deprecated option**: Rejected because the issue requires `init` to exit nonzero and name `--published` when callers pass it, and to remove it from help and docs. [sources: src/devops_cli/commands/devcontainer.py:111-118]
- **Removing `published` from `devcontainer.json.j2` as well**: Rejected because `init`'s recorded render context requirement specifies that `render_json_template` receives `image` and `published` and omits `python_version`, and `tests/core/test_template_rendering.py` tests `published` directly. [sources: tests/core/test_template_rendering.py:104-107]
