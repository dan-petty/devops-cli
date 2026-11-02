# Proposal

## Why

Issue #2651: the error text of the kubectl fallback of `devops k8s logs` tells a person to "Configure loki.url", but no such setting exists. `devops config set loki.url <url>` fails with `Unknown config key`. The command, its `--dry-run` plan, the live log pane and the MCP tool `k8s_logs` dial the constant `DEFAULT_LOKI_URL` (`http://localhost:3100`) when `--loki-url` is absent, and a person cannot change that address in the configuration. The spec `k8s-logs` names `loki.url` in four scenarios.

## What Changes

- Add the setting `loki.url` (`LokiConfig` in `src/devops_cli/config/settings.py`). It is unset by default, takes an `http` or `https` URL, and has the variable `DEVOPS_CLI_LOKI_URL`.
- Add `resolve_loki_url` to `src/devops_cli/k8s/logql.py`: the option `--loki-url`, else `loki.url`, else `DEFAULT_LOKI_URL`. `execute_logql_query` and `plan_k8s_logs` (`src/devops_cli/k8s/cluster_plans.py`) call it. This covers the command, the MCP tool, the live log pane (`LokiLogSource` in `src/devops_cli/ui/widgets.py`) and the dry-run plan. The tool still publishes no `loki_url`.
- Name `loki.url` in the help of `--loki-url` (`src/devops_cli/commands/k8s/cluster_context.py`) and regenerate the documents.
- Spec delta: `configured-service-urls` gets one ADDED requirement (the key). `k8s-logs` gets one ADDED requirement (the address order and its egress level) and one MODIFIED requirement (the definition of "the default Loki" and its scenarios). The change is observable, so it carries a delta.
- Unchanged: the error text of the fallback (`src/devops_cli/k8s/logql.py:272`) already names `loki.url`, and the key now exists. The default address stays `http://localhost:3100`, as the spec scenario "The default Loki" requires. `devops k8s configure-urls` does not write `loki.url`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `configured-service-urls`: The Loki address is a setting
- `k8s-logs`: The Loki address of a log query; The MCP tool k8s_logs publishes no Loki URL

## Impact

- Code: `src/devops_cli/config/settings.py`, `src/devops_cli/k8s/logql.py`, `src/devops_cli/k8s/cluster_plans.py`, `src/devops_cli/commands/k8s/cluster_context.py` (help text only).
- Tests: `tests/config/test_loki_url.py`, `tests/k8s/test_loki_url_setting.py`, `tests/commands/k8s/test_k8s_logs_loki_url.py` (all new), `tests/ai/mcp/test_k8s_logql.py` and `tests/security/test_config_declarations.py` (edited).
- Documents (generated): `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`, `docs/CLI_REFERENCE.md`, `docs/commands/k8s.md`.
- Egress and trust: the Loki client dials at the private level (`src/devops_cli/k8s/logql.py:396`, `EgressLevel.PRIVATE`), and the setting keeps that level. A person writes `loki.url`. The MCP exposure table holds no `config set` (`src/devops_cli/config/constants.py:301-303` lists `config audit-keys`, `output` and `show`), so a model cannot change the address.

## Feasibility

Checked on `origin/main` at `24ef67ac` (`devops --version` prints `0.45.0`).

- The premise holds. `uv run devops config set loki.url http://example.com:3100` exits 1 and prints `Unknown config key: 'loki.url'` and `Known keys with a similar name: valkey.url`. `src/devops_cli/config/settings.py` has `TempoConfig` (line 357) and `PyroscopeConfig` but no Loki class.
- The readers of the address: `git grep -n "DEFAULT_LOKI_URL"` in `src/` finds `logql.py:379` (default of `execute_loki_query`), `logql.py:473` (`url = loki_url or DEFAULT_LOKI_URL` in `execute_logql_query`) and `cluster_plans.py:112` (`plan_k8s_logs`). `execute_logql_query` has three callers: `commands/k8s/cluster_context.py:453`, `ui/widgets.py:211` and `ui/widgets.py:229`. The MCP tool `k8s_logs` is the command itself: `src/devops_cli/ai/mcp/generator.py:76` lists its parameters.
- A prototype in a scratch clone (not committed) with `url: Annotated[HttpUrlStr | None, Variable()]` in a new `LokiConfig`: `devops config set loki.url http://example.com:3100` exits 0 and prints `loki.url = http://example.com:3100`. `devops config set loki.url k8s://logging/loki:3100` exits 1 and prints `Failed to set 'loki.url': loki.url: URL scheme should be 'http' or 'https'`.
- The type is `HttpUrlStr`, not `ServiceUrlStr`. The Loki client dials only `http` and `https`: `httpx2.UnsupportedProtocol` is a `TransportError`, which `execute_logql_query` (`logql.py:497`) does not catch, so a `k8s://` value that `ServiceUrlStr` accepts would end every query in a traceback.
- The variable has a cost that the prototype showed: `tests/security/test_config_declarations.py::test_the_variables_are_those_before_one_for_each_read_option_that_had_none_and_later_ones` failed on `DEVOPS_CLI_LOKI_URL` until the name joined `_VARIABLES_OF_LATER_SETTINGS`. With that name added, `pytest tests/config tests/security tests/docs tests/lang tests/invariants` gave 2165 passed and 1 failed (`test_this_repository_passes_the_argocd_gate`, which needs a GitHub `origin` and fails in the sandbox only).
- `uv run devops docs generate --sync-readme` after the prototype changed `docs/CONFIGURATION.md` (8 lines) and `docs/ENV_VARS.md` (1 line); `uv run devops docs check` then passed.
- Egress of a configured address, with `ai.allow_private_network` false and a scripted resolver on `main`: a host that answers `127.0.0.1` or `192.0.2.10` is dialled; a host that answers `169.254.169.254` raises `SSRFBlockedError` and gets no dial. So the private level applies, and cloud metadata stays refused.
- `acceptance_criteria` (`src/devops_cli/roadmap/stage_criteria.py`) returns an empty list for the body of #2651: the criteria sit in the refine block, which the check cuts off. The tasks hold no `## Criteria` section. The five criteria of the refine block map to the specs: the key (`configured-service-urls`), the command, the MCP tool, the default and the fallback text (`k8s-logs`).

## Existing Tool Considered

`pydantic-settings` is the open, maintained library that already holds the settings layer (`src/devops_cli/config/settings.py:34`). The change adds one field to it, in the form of `tempo.url` and `grafana.url`, so it builds no new configuration code. The cost of this plan: about 30,000 tokens to write the 3 source edits and the 4 test files, 10,000 tokens to keep the generated documents in step, and about 45 minutes of elapsed time. The upkeep is one field and one function. The change deletes two expressions, `loki_url or DEFAULT_LOKI_URL` in `logql.py` and `cluster_plans.py`, and the import of `DEFAULT_LOKI_URL` in `cluster_plans.py`.
