# devcontainer-init-options Specification

## Purpose

Enforce that `devops devcontainer init` exposes only effective options (removing dead `--published` and `--python` and omitting `python_version` from its render context) while keeping `update --python` and docs aligned.

## Requirements

### Requirement: Init help hides removed options
The `init` command of `devops devcontainer` SHALL show neither `--published` nor `--python` in its help.

#### Scenario: Help of init
- **WHEN** A test runs `devops devcontainer init --help` in the CLI runner.
- **THEN** The output holds no `--published`, no `-p` and no `--python`.

### Requirement: Init rejects removed options
The `init` command of `devops devcontainer` SHALL exit with a nonzero code when a caller passes `--published` or `--python`.

#### Scenario: Removed option use
- **WHEN** A test runs `devops devcontainer init --published` in the CLI runner.
- **THEN** The command exits with a nonzero code and its output names `--published`.

### Requirement: Init render context
The `init` command SHALL NOT pass `python_version` to `devcontainer.json.j2`.

#### Scenario: Recorded render arguments
- **WHEN** A test replaces `render_json_template` with a recorder and runs `init` on a temporary directory.
- **THEN** The recorded keyword arguments hold `image` and `published`, and they hold no `python_version`.

### Requirement: Update keeps the Python option
The `update` command SHALL keep `--python` and SHALL set the manifest image from its value.

#### Scenario: Update writes the image
- **WHEN** A test runs `devops devcontainer update --python 3.13` on a directory that holds a manifest.
- **THEN** The written `image` starts with `CONST_DEVCONTAINER_IMAGE_PREFIX` and ends with `3.13`.

### Requirement: Command reference is current
The generated command reference SHALL show `devcontainer init` with no `--published` and no `--python`.

#### Scenario: Docs row of static analysis
- **WHEN** `uv run devops ci --check --only docs` runs on the change.
- **THEN** The docs row reports a pass and no stale generated document.

### Requirement: Usage guide shows no removed option
`docs/DEVCONTAINER_USAGE.md` SHALL NOT show `init --published`.

#### Scenario: Search of the usage guide
- **WHEN** `rg -n -- '--published' docs/DEVCONTAINER_USAGE.md` runs.
- **THEN** The command prints no line.
