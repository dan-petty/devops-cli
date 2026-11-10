# Tasks

## 1. Install the locked tools in the image

Reads: `src/devops_cli/commands/install_tools.py`. Changes: `.devcontainer/Dockerfile`, `src/devops_cli/commands/devcontainer.py`, `src/devops_cli/devcontainer/devcontainer_plans.py`, `tests/invariants/test_devcontainer_config.py`, `tests/commands/test_devcontainer.py`.

- [x] 1.1 In `tests/invariants/test_devcontainer_config.py` and `tests/commands/test_devcontainer.py`, assert that the image build uses native steps, pins what `tools.lock` pins and installs under `/usr/local` and that post-create installs no tool
  - Verification: `$ uv run devops ci test tests/invariants/test_devcontainer_config.py tests/commands/test_devcontainer.py` passes
- [x] 1.2 In `.devcontainer/Dockerfile`, get every locked tool with native steps of Docker and the package managers, and remove the tool bootstrap, `--skip-tools` and the install step of the plan with their tests
  - Verification: `$ uv run devops ci test tests/invariants/test_devcontainer_config.py tests/commands/test_devcontainer.py` passes

## 2. Documents

- [x] 2.1 In `docs/DEVCONTAINER_USAGE.md`, `docs/commands/devcontainer.md` and `docs/CLI_REFERENCE.md`, say that the image holds the tools and remove `--skip-tools`
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Pending a person: build the image once (`docker build -f .devcontainer/Dockerfile .`) and time it, because the build environment of the author could not pull the base image.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
