# Tasks

## 1. Implement `tf/github` agent guards, config, and reader credentials

Kind: python. Reads: `src/devops_cli/commands/tf.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/infra/access.py`, `src/devops_cli/github/app_installation.py`. Changes: `src/devops_cli/tf/access.py`, `src/devops_cli/commands/tf.py`, `src/devops_cli/config/{constants,defaults,env,settings}.py`, `src/devops_cli/exceptions/{__init__,tf}.py`, `src/devops_cli/lang/en/errors.py`, `tests/`.

- [x] 1.1 Write failing unit, config-validation, and CLI tests for `tf.stacks[].agent_access`, core budget floor (249 vs 250), `tf.github_reader` token minting / missing credentials, zero-request `--dry-run`, and `SECURITY.md`
  - Verification: `$ uv run pytest tests/tf/test_access.py tests/config/test_tf_stacks_setting.py tests/commands/test_tf.py`
- [x] 1.2 Implement `TFConfig` / `tf.github_reader` settings, `src/devops_cli/tf/access.py`, `tf_plan`/`tf_apply`/`tf_destroy` integration, `tests/security/test_config_declarations.py` declarations, and `SECURITY.md` `## GitHub Settings` section
  - Verification: `$ uv run pytest tests/tf/test_access.py tests/config/test_tf_stacks_setting.py tests/commands/test_tf.py tests/security/test_config_declarations.py`

## 2. Regenerate docs and run full verification

Kind: python. Reads: `SECURITY.md`, `src/devops_cli/config/settings.py`. Changes: `docs/`.

- [x] 2.1 Regenerate docs (`devops docs generate`), archive OpenSpec, run `devops ci --check --skip test --force`, and run `devops ci fail-to-pass --base origin/main`
  - Verification: `$ uv run devops ci --check --skip test --force && uv run devops ci fail-to-pass --base origin/main`
