# Tasks

## 1. Make a dry run of config unset write nothing and print the redacted diff

Reads: `src/devops_cli/commands/config.py`, `src/devops_cli/config/settings.py`, `tests/commands/test_config.py`. Changes: `src/devops_cli/commands/config.py`, `tests/commands/test_config.py`.

- [ ] 1.1 In `tests/commands/test_config.py`, rewrite `test_config_unset_dry_run_runs_as_no_external_request` so it runs `devops --dry-run config unset ai.vllm_url` on a config that holds the key, and asserts exit 0, the unchanged file text, no `.yaml.bak-` file in the directory, and diff lines `@@ -7 +6,0 @@` and `-  vllm_url: http://192.0.2.10:8000` in the output. Add a case with a credential key whose value shows as `***REDACTED***` and whose value is absent from the output, and verify that `uv run devops ci test tests/commands/test_config.py` fails on the base
- [ ] 1.2 In `unset_value` at `src/devops_cli/commands/config.py`, read the dry-run state, pass it to `remove_config_key(key, dry_run=<flag>)`, and when it is a dry run print the response with the key, the path, the line and `removal.diff`, with the value of each path in `write_history.credential_paths` replaced by `***REDACTED***`, then return before the success and backup messages. Keep the existing messages and the backup copy for a real run, and verify that `uv run devops ci test tests/commands/test_config.py` passes

## 2. State the dry-run diff and the redaction in the config-commands spec

Reads: `openspec/specs/config-commands/spec.md`, `src/devops_cli/commands/config.py`. Changes: `openspec/specs/config-commands/spec.md`.

- [ ] 2.1 Update the requirement `devops config unset --dry-run writes nothing` in `openspec/specs/config-commands/spec.md` so it states the printed file, key, line and unified diff, the redacted credential value, and that no file, backup or audit record is written. Add the credential scenario beside the existing one, and verify that `uv run devops openspec check` passes
- [ ] 2.2 openspec/specs/config-commands/spec.md, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Criteria

- A dry run of `config unset` writes nothing: it does not change the config file and does not write a backup.: group 1
- It prints the diff of the removal, with the value of a credential key redacted. `write_history.credential_paths` is the source of the credential key paths.: group 1
- The test at `tests/commands/test_config.py:158` asserts the new behavior.: group 1
- The spec and the code agree.: group 2

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
