# Tasks

## 1. Add loki.url config key to settings

Reads: none. Changes: `src/devops_cli/config/settings.py`, `tests/test_loki_url_config.py` (new).

- [ ] 1.1 test_loki_url_config_key: run devops config set loki.url http://example.com:3100 and assert the command exits with code 0, and verify that `uv run pytest tests/test_loki_url_config.py -v` fails on the base
- [ ] 1.2 Add a LokiConfig Pydantic model with a url field of type ServiceUrlStr | None, defaulting to None. Add loki: LokiConfig = LokiConfig() to the Settings class, alongside qdrant, tempo, pyroscope and valkey. Import DEFAULT_LOKI_URL from devops_cli.config.defaults for reference in the field description, and verify that `uv run pytest tests/test_loki_url_config.py -v` passes

## 2. Wire loki.url into k8s logs command

Reads: none. Changes: `src/devops_cli/k8s/logql.py`.

- [ ] 2.1 test_k8s_logs_uses_configured_loki_url: set loki.url to http://example.com:3100, run devops k8s logs without --loki-url, and assert the HTTP request is sent to http://example.com:3100/loki/api/v1/query_range, and verify that `uv run pytest tests/ai/mcp/test_k8s_logql.py -v` fails on the base
- [ ] 2.2 In the logql query path, read settings.loki.url. When --loki-url is not given, use settings.loki.url if set, else DEFAULT_LOKI_URL. The MCP tool k8s_logs calls the same function, so it reads the same setting. The --loki-url flag overrides the setting when both are present, and verify that `uv run pytest tests/ai/mcp/test_k8s_logql.py -v` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
