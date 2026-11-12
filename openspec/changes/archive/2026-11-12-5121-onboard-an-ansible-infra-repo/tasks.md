# Tasks

## 1. Behavior

- [x] 1.1 Write failing tests: `infra.repos` entries and their default level, the caller kinds, the `[python.ansible-core]` pin, the project profile layers and sources, the 17 rows for a complete repo and for a repo that lacks each item, and the command (agent refusal, confirm, kept level, local folder, dry run)
  - Verification: `$ uv run devops ci test tests/config/test_infra_repos_setting.py tests/core/test_caller.py tests/tools_lock/test_tools_lock.py tests/project/test_profile.py tests/infra/test_onboard.py tests/commands/test_infra_onboard.py`
- [x] 1.2 Add the `infra` settings, the project profile loader with the `ansible-k8s` template, `core/caller.py` (moved from `telemetry/usage_errors.py`), the `[python.ansible-core]` tool and its step in the devcontainer image, the `devops infra` group and `devops infra onboard` with its rows, its write and its dry run
  - Verification: `$ uv run devops ci test tests/config/test_infra_repos_setting.py tests/core/test_caller.py tests/tools_lock/test_tools_lock.py tests/project/test_profile.py tests/infra/test_onboard.py tests/commands/test_infra_onboard.py tests/telemetry/test_usage_errors.py tests/ai/mcp tests/commands/test_all_commands_help_dryrun.py tests/invariants/test_devcontainer_config.py`

## 2. Documents

- [x] 2.1 Regenerate the command reference, the configuration and variables reference, the error catalog and the README command matrix; add the terms infra repo, agent access level and project profile to `CONTEXT.md`
  - Verification: `$ uv run devops ci --check --only docs`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
- Pending a person: set dan-petty/homelab to full: `uv run devops infra onboard dan-petty/homelab --agent-access full --confirm`.
