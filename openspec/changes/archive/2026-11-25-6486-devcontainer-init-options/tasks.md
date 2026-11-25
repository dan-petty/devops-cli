# Tasks

## 1. Tests first

- [x] 1.1 Update and add failing tests in `tests/commands/test_devcontainer.py` covering `init --help`, nonzero exit on `--published` / `--python`, recorded `render_json_template` keyword arguments (`image` and `published` present, `python_version` absent), and `update --python 3.13`
  - Verification: `$ uv run pytest -n 0 tests/commands/test_devcontainer.py -k "TestInitAndUpdate or init"`

## 2. Remove unused options and update docs

- [x] 2.1 Remove `--published`/`-p` and `--python` and the `python_version` render argument from `init` in `src/devops_cli/commands/devcontainer.py`, remove unused `published` help field from `src/devops_cli/lang/en/help.py`, remove `init --published` from `docs/DEVCONTAINER_USAGE.md`, and run `uv run devops docs generate`
  - Verification: `$ uv run pytest -n 0 tests/commands/test_devcontainer.py tests/core/test_template_rendering.py tests/lang/ && uv run devops ci --check --skip test`

Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
