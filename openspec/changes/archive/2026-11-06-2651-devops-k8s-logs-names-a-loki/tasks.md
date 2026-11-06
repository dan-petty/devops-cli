# Tasks

## 1. The setting `loki.url`

Reads: `src/devops_cli/config/settings.py`, `tests/config/test_config_keys.py`. Changes: `src/devops_cli/config/settings.py`, `tests/security/test_config_declarations.py`, `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`, `tests/config/test_loki_url.py` (new).

- [x] 1.1 Write failing tests in `tests/config/test_loki_url.py` for the scenarios of "The Loki address is a setting": `config set` writes `loki.url`, `config set` refuses a `k8s://` value and names `loki.url`, and `DEVOPS_CLI_LOKI_URL` sets it. Add `DEVOPS_CLI_LOKI_URL` to `_VARIABLES_OF_LATER_SETTINGS` in `tests/security/test_config_declarations.py`.
  - Verification: `uv run devops ci test tests/config/test_loki_url.py tests/security/test_config_declarations.py` (fails on the base)
- [x] 1.2 Add `LokiConfig` with `url: Annotated[HttpUrlStr | None, Variable()]` (default `None`, with a description) before `TempoConfig` in `settings.py`, and `loki: LokiConfig = LokiConfig()` in `Settings` before `tempo`, and the `loki` section title in `CONST_SETTINGS_SECTION_METADATA`.
  - Verification: `uv run devops ci test tests/config/test_loki_url.py tests/security/test_config_declarations.py`
- [x] 1.3 Regenerate the documents for the new key and variable with `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops docs check`

## 2. One address for every Loki query

Reads: `src/devops_cli/k8s/logql.py`, `src/devops_cli/k8s/cluster_plans.py`, `src/devops_cli/commands/k8s/cluster_context.py`, `src/devops_cli/ui/widgets.py`, `tests/web_fakes.py`, `tests/http/test_http_egress.py`. Changes: `src/devops_cli/k8s/logql.py`, `src/devops_cli/k8s/cluster_plans.py`, `src/devops_cli/commands/k8s/cluster_context.py`, `tests/ai/mcp/test_k8s_logql.py`, `docs/CLI_REFERENCE.md`, `docs/commands/k8s.md`, `tests/k8s/test_loki_url_setting.py` (new), `tests/commands/k8s/test_k8s_logs_loki_url.py` (new).

- [x] 2.1 Write failing tests for the scenarios of "The Loki address of a log query" and of the MODIFIED "The MCP tool k8s_logs publishes no Loki URL". In `tests/k8s/test_loki_url_setting.py`: `execute_logql_query` and `plan_k8s_logs` use the setting, an argument wins, neither gives `localhost:3100`, a host that answers `127.0.0.1` or `192.0.2.10` is dialled with `ai.allow_private_network` false, and a host that answers `169.254.169.254` raises `SSRFBlockedError` with no dial. In `tests/commands/k8s/test_k8s_logs_loki_url.py`: `devops k8s logs` uses the setting, `--loki-url` wins, `--dry-run` shows the setting, and `devops k8s logs --help` names `loki.url`. In `tests/ai/mcp/test_k8s_logql.py`: the tool queries the setting, and a call with `loki_url` fails with no dial when the setting is set.
  - Verification: `uv run devops ci test tests/k8s/test_loki_url_setting.py tests/commands/k8s/test_k8s_logs_loki_url.py tests/ai/mcp/test_k8s_logql.py` (fails on the base)
- [x] 2.2 Add `resolve_loki_url(loki_url: str | None = None) -> str` to `logql.py` (option, else `load_settings().loki.url`, else `DEFAULT_LOKI_URL`). Call it in `execute_logql_query` in place of `loki_url or DEFAULT_LOKI_URL`, and in `plan_k8s_logs` in place of the same expression. Delete the import of `DEFAULT_LOKI_URL` in `cluster_plans.py`. Change the help of `--loki-url` in `cluster_context.py` to "Loki service endpoint; overrides the `loki.url` setting (default: http://localhost:3100)".
  - Verification: `uv run devops ci test tests/k8s/test_loki_url_setting.py tests/commands/k8s/test_k8s_logs_loki_url.py tests/ai/mcp/test_k8s_logql.py tests/commands/test_k8s_dry_run.py tests/http/test_http_egress.py`
- [x] 2.3 Regenerate the documents for the new help with `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops docs check`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
