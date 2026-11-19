# Tasks

## 1. Name the install command in the project profile

Kind: behavior. Reads: `src/devops_cli/project/profile.py`, `src/devops_cli/templates/profiles/ansible-k8s.toml`, `tests/project/test_profile.py`, `src/devops_cli/infra/onboard.py`, `tests/infra/test_onboard.py`. Changes: `src/devops_cli/project/profile.py`, `src/devops_cli/templates/profiles/ansible-k8s.toml`, `tests/project/test_profile.py`, `tests/infra/test_onboard.py`, `tests/commands/__snapshots__/test_infra_onboard.ambr`.
Adds: `ToolsProfile`

- [x] 1.1 `test_an_ansible_cfg_makes_the_type_and_gives_the_layout` and `test_the_project_file_turns_off_the_install_command_of_the_template` in `tests/project/test_profile.py`
  - Verification: `$ uv run devops ci test tests/project/test_profile.py` fails on the base
- [x] 1.2 Add `ToolsProfile` with `install: list[str]` and the field `tools` of `ProjectProfile`, and `[tools] install = ["make", "install"]` to the template. The onboarding row of the profile lists the new value with its source
  - Verification: `$ uv run devops ci test tests/project/test_profile.py tests/infra/test_onboard.py tests/commands/test_infra_onboard.py` passes

## 2. Install the tools of each infra repo at post-start

Kind: behavior. Reads: `src/devops_cli/commands/devcontainer.py`, `src/devops_cli/devcontainer/devcontainer_plans.py`, `src/devops_cli/infra/onboard.py`, `src/devops_cli/core/process.py`, `tests/support/fakes/process.py`, `tests/commands/test_devcontainer.py`. Changes: `src/devops_cli/infra/tools.py`, `src/devops_cli/commands/devcontainer.py`, `src/devops_cli/devcontainer/devcontainer_plans.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/lang/en/messages.py`, `tests/infra/test_tools.py`, `tests/commands/test_devcontainer.py`.
Adds: `install_repo_tools`, `plan_repo_tools`, `DEFAULT_INFRA_TOOLS_INSTALL_TIMEOUT_SECONDS`

- [x] 2.1 The tests of `tests/infra/test_tools.py`, and `test_post_start_installs_the_tools_of_each_infra_repo` and `test_post_start_dry_run_plans_the_install_of_each_infra_repo` in `tests/commands/test_devcontainer.py`
  - Verification: `$ uv run devops ci test tests/infra/test_tools.py` fails on the base
- [x] 2.2 Add `install_repo_tools(settings, dry_run=...)` and `plan_repo_tools(settings)` to `src/devops_cli/infra/tools.py`. Call the first from `_run_post_start_lifecycle` after the pre-commit step, and add the requests of the second to `plan_post_start` after the git requests
  - Verification: `$ uv run devops ci test tests/infra/test_tools.py tests/commands/test_devcontainer.py` passes

## 3. Documents

Kind: documents. Changes: `CONTEXT.md`, `ARCHITECTURE.md`, `docs/DEVCONTAINER_USAGE.md`, `docs/CLI_REFERENCE.md`, `docs/commands/devcontainer.md`.

- [x] 3.1 Name the key in the term "Project profile" of `CONTEXT.md`, the step in the lifecycle diagram of `ARCHITECTURE.md` and in "The Devcontainer of This Repository" of `docs/DEVCONTAINER_USAGE.md`, and regenerate the command documents for the new help text of post-start
  - Verification: `$ uv run devops docs generate` leaves no change
- Pending a person: rebuild or restart the devcontainer after dan-petty/homelab#62 merges, and check that post-start prints `Installed the tools of dan-petty/homelab`.
