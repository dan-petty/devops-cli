# Tasks

## 1. devops config init names the file that it writes

- [x] 1.1 Write `test_config_init_names_the_active_config_file_it_writes` in `tests/commands/test_config.py`, and verify that `uv run devops ci test tests/commands/test_config.py` fails on the base because the `Config file:` line names the default config path
- [x] 1.2 Make `init` in `src/devops_cli/commands/config.py` resolve the active config path one time, give it to `save_settings`, and show it, and remove the unused `CONST_CONFIG_PATH` import, and verify that `uv run devops ci test tests/commands/test_config.py tests/test_config_commands.py` passes
- [x] 1.3 Verify that the generated command documentation does not change (`uv run devops docs generate --sync-readme`, then `uv run devops docs check`)

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
