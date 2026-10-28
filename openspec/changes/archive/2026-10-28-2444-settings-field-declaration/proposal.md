# Proposal

## Why

Issue #2444, part 1 of #1000: six hand-written registries described the settings, and they disagreed.

- `config/options.py` held 100 key constants, `CONFIG_OPTIONS`, `SECRET_CONFIG_OPTIONS` and `KEYRING_KEYS`.
- `config/env.py` held 84 `ENV_*` constants, the `OPTION_TO_ENV_VAR` map and the hand-written `get_all_env_var_specs()` list of 79 specs.
- `security/secrets.py` repeated the keyring name and the variables of each of the 15 credentials, and `k8s/cluster_secrets.py` repeated the keyring names of 9 of them again.
- `config/settings.py` held `_CHILD_DATA_ENV_MAP`, a seventh copy of 12 variable names.
- `devops config show` printed 29 hand-written `_row` lines, a part of the options.

Measured drift on origin/main 4226904e: `devops config env` and `docs/ENV_VARS.md` did not show 7 variables that set a setting (`DEVOPS_CLI_AI_TASK_<TASK>_REASONING_EFFORT` for 4 tasks, `DEVOPS_CLI_AI_RAG_ENABLED`, `_TOP_K` and `_SCORE_THRESHOLD`), nor 6 variables that the credential resolver reads (`DEVOPS_CLI_GRAFANA_PASSWORD`, `DEVOPS_CLI_ARGOCD_PASSWORD`, `DEVOPS_CLI_TELEMETRY_LOGFIRE_TOKEN`, `LOGFIRE_TOKEN`, `FIRECRAWL_API_KEY`, `CLOUDFLARE_API_TOKEN`). 13 options read no variable, and `CONFIG_OPTIONS` had no reader outside `options.py`.

## What Changes

- A settings field declares that a variable sets it with a `Variable` marker in `Annotated` metadata, and its description with `Field(description=...)`. The variable is `DEVOPS_CLI_` and the dotted key in upper case, with `_` for `.`. The `tasks` field of `ai` declares the segment `TASK`, so the 17 task variables keep their names, and each task field of `ai.tasks` names the fields of its shared model that a variable sets.
- A credential is one entry of `CREDENTIALS` in `config/env.py`: its key, its description, its other variables, whether the config file may hold it, and its keyring name when that is not the key with `_` for `.`.
- `setting_variables()`, `option_env_vars()`, `env_var_for_option()`, `secret_keys()`, `keyring_names()` and `get_all_env_var_specs()` derive every list from the two declarations. The env overrides, the data directory variables, `build_secret_registry()`, `KeyringSource.for_credential()`, the commands, the docs generator and the workspace route read them.
- `devops config show` prints every setting that a variable sets and every credential, sorted by key, and has `--format` and `--json`. A credential shows as set or not set.
- The 10 options that code reads and that had no variable get one: `ai.reference_model`, `ai.reference_embedding_model`, `ai.reference_provider`, `ai.hardware_cost_usd`, `telemetry.capture_llm_content`, `sandbox.exclude_home_dir`, `cloudflare.public_ip_bypass`, `cloudflare.access.allowed_emails`, `cloudflare.access.bypass_ips` and `cloudflare.access.public_ip_bypass`. The 3 options that no code reads (`telemetry.logfire`, `cloudflare.access.enabled`, `cloudflare.access.idp`) get none; #2457 handles them.
- `config/options.py`, the `ENV_*` constants of settings, the `OPTION_TO_ENV_VAR` and `ENV_VAR_TO_OPTION` maps, the hand-written spec list, `_CHILD_DATA_ENV_MAP` and the `_row` lines are deleted. Code names a setting by its dotted key.
- The commands change what a person sees, so the change carries a spec delta in `config-commands`.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `config-commands`: `devops config show` and `devops config env` list every declared setting and credential, and the variable of a setting follows one rule.

## Impact

- `src/devops_cli/config/env.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/options.py` (deleted).
- `src/devops_cli/commands/config.py`, `src/devops_cli/security/secrets.py`, `src/devops_cli/docs/generator.py`, and the modules that read a key constant or a variable constant: `commands/ai.py`, `commands/serve.py`, `commands/telemetry.py`, `commands/ai_runs.py`, `commands/k8s/networking.py`, `k8s/cluster_secrets.py`, `k8s/configmap.py`, `k8s/gitea_doctor.py`, `github/app_installation.py`, `ai/client/models.py`, `ai/run_store.py`, `ai/spend/ledger.py`, `roadmap/run.py`, `review/session.py`, `server/routes/workspace.py`.
- The tests that read the deleted names, `tests/support/fakes/valkey.py`, the floor's reset table in `tests/conftest.py`, and the new `tests/test_config_declarations.py`.
- `CONTRIBUTING.md` (the naming row of a variable), and `docs/ENV_VARS.md`, `docs/CONFIGURATION.md`, `docs/commands/config.md`, `docs/CLI_REFERENCE.md`, `docs/MCP_TOOLS.md` and `README.md`, which `devops docs generate --sync-readme` rewrites.

## Feasibility

- On origin/main 4226904e, `load_settings` built `Settings` with `model_validate`, so pydantic-settings read no variable, and `_apply_env_overrides` applied each one from `OPTION_TO_ENV_VAR`. The registries listed above were read with `git grep` and compared in a script: 92 variables in all, 7 setting variables with no spec, 13 options with no variable, 3 of them read by no code.
- 67 of the 84 mapped names follow the rule `DEVOPS_CLI_` and the key in upper case. The other 17 are all `ai.tasks.<task>.*`, which the variables spell `AI_TASK_`. The names appear in `k8s/README.md`, `docs/SELF_IMPROVEMENT.md`, the knowledge base and `openspec/specs/ai-task-models/spec.md`, so they stay, and one segment declaration keeps them.
- pydantic keeps an object of an `Annotated` type in `FieldInfo.metadata` (pydantic 2.12), so a field's own declaration holds the marker. A test (`test_the_variables_are_those_before_and_one_for_each_read_option_that_had_none`) holds the set of variables to the 92 names before the change and the 10 added.
- `CONST_GITHUB_APP_PRIVATE_KEY_ENV` stays: `core/process.py` reads it below the settings layer. A test holds it equal to the derived name.

## Existing Tool Considered

pydantic field metadata holds the declaration, and pydantic-settings' `Field(description=...)` its text. pydantic-settings' own variable binding is not used here: it joins nested names with `env_nested_delimiter`, which cannot give the `AI_TASK_` names or the variables of a model that several fields share. Its sources are part 2 of #1000 (#2445). The change builds a walk of about 40 lines over `model_fields`, and deletes `config/options.py` (279 lines), the hand-written parts of `config/env.py` (about 600 lines), the credential table of `build_secret_registry`, `_CHILD_DATA_ENV_MAP` and the 29 `_row` lines.
