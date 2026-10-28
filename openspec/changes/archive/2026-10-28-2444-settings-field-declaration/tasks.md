# Tasks

## 1. Each setting is declared once, and every list is derived from it

- [x] Add failing tests: the set of variables is the set before the change and the 10 added; the keyring names and secret keys are those before; `config env` lists every setting and credential variable with a description; `config show --json` prints every setting and credential once and masks a credential; an added variable sets its setting; `config/options.py` does not exist
  - Verification: `uv run devops ci test tests/test_config_declarations.py`
- [x] Add the `Variable` marker, the `CREDENTIALS` table and the derived views in `config/env.py`, mark the settings fields and give each one a description, and build the env overrides, the data directory variables and `build_secret_registry()` from them
  - Verification: `uv run devops ci test tests/test_config_declarations.py tests/test_config_env_overrides.py tests/test_secret_resolution.py tests/test_data_dir_configuration.py`
- [x] Rewrite `config show` over the declared settings with `--format` and `--json`, and move `config env`, `config audit-keys`, `config auth-headless`, the docs generator, the workspace route and `KeyringSource.for_credential()` to the derived views
  - Verification: `uv run devops ci test tests/test_config_cmd.py tests/test_k8s_push_secrets.py tests/test_headless_auth.py`
- [x] Delete `config/options.py`, the `ENV_*` constants of settings, `OPTION_TO_ENV_VAR`, `ENV_VAR_TO_OPTION`, the hand-written spec list, `_CHILD_DATA_ENV_MAP` and the `_row` lines, and name each setting by its dotted key in code and tests
  - Verification: `uv run devops ci test tests/test_config_declarations.py tests/test_valkey.py tests/test_k8s_qdrant_security.py tests/test_k8s_devops_runtime.py tests/test_k8s_roadmap_service.py tests/test_k8s_argo_workflows.py`
- [x] Register `reset_declarations_cache` in the floor's reset table
  - Verification: `uv run devops ci test tests/test_architectural_invariants.py`
- [x] Describe the variable rule in `CONTRIBUTING.md` and regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 2. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 2444-settings-field-declaration`
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

## Workflow follow-up

- #2445: one resolution order through pydantic-settings sources.
- #2447: field-backed defaults are read only through the settings.
- #2457: the 3 options that no code reads (`telemetry.logfire`, `cloudflare.access.enabled`, `cloudflare.access.idp`).
