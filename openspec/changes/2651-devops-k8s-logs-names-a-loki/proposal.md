# Proposal

## Why

Issue #2651: devops k8s logs tells a user to configure loki.url, but that key does not exist in the config system. The command dials DEFAULT_LOKI_URL (http://localhost:3100) when no --loki-url flag is given, and a user cannot set the Loki address in the configuration. The spec k8s-logs names loki.url in four scenarios, and the spec configured-service-urls lists Qdrant, Tempo, Pyroscope and Vault but not Loki.

## What Changes

- Add LokiConfig class to src/devops_cli/config/settings.py with a url field of type ServiceUrlStr | None
- Register loki in the Settings class alongside qdrant, tempo, pyroscope and valkey
- Wire loki.url into the logql query path in src/devops_cli/k8s/logql.py so both the CLI command and the MCP tool read the configured address
- Add spec requirements to k8s-logs and configured-service-urls capabilities
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `k8s-logs`: loki-url-config-setting
- `configured-service-urls`: loki-url-config-key

## Impact

- Code: `src/devops_cli/config/settings.py`, `src/devops_cli/k8s/logql.py`
- Tests: `tests/test_loki_url_config.py`

## Feasibility

- The inputs confirm the premise: src/devops_cli/config/settings.py has no LokiConfig class and no loki field in Settings. The #2635 archived proposal states 'The settings hold no Loki key' and 'src/devops_cli/config/settings.py has none'. The issue shows the error 'Unknown config key: loki.url'.
- First check: run `devops config set loki.url http://example.com:3100` and confirm it exits 0 after the fix.
- Second check: set loki.url to a test address, run `devops k8s logs '{app=~"x"}'` without --loki-url, and confirm the HTTP request goes to the configured address.

## Existing Tool Considered

No external tool covers this. The project builds its own config layer in src/devops_cli/config/. The written cost is the tokens to add the key to settings.py, update the call site in k8s/logql.py, and add tests, plus the time to keep the key in sync with the spec and the defaults file.
