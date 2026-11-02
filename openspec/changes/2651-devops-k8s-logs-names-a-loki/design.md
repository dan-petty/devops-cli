# Design

## Decisions

- **The key is `loki.url`**: It matches `qdrant.url`, `tempo.url`, `grafana.url` and `valkey.url`, and the text in `logql.py:272` and in the spec `k8s-logs`.
- **The type is `HttpUrlStr`, not `ServiceUrlStr`**: The Loki client dials only `http` and `https`. A `k8s://` value would pass `ServiceUrlStr` and then raise `httpx2.UnsupportedProtocol` in every query, with no fallback (`logql.py:497` catches `ConnectError` and `TimeoutException` only). `config set` refuses such a value at once and names `loki.url`.
- **The field has a `Variable()` marker**: `DEVOPS_CLI_LOKI_URL` follows the rule in `tests/security/test_config_declarations.py` for an option that code reads. That test lists each variable, so the name joins `_VARIABLES_OF_LATER_SETTINGS`.
- **One function resolves the address**: `resolve_loki_url(loki_url)` in `logql.py` returns the option, else `load_settings().loki.url`, else `DEFAULT_LOKI_URL`. `execute_logql_query` and `plan_k8s_logs` both call it, so the real query and the dry-run plan name the same host. `LokiLogSource` in `ui/widgets.py` calls `execute_logql_query` and needs no edit. `execute_loki_query` keeps its explicit `loki_url` parameter.
- **The option wins over the setting**: An explicit option is the most specific instruction. The code already gave it priority over the constant.
- **The default stays `http://localhost:3100`**: The spec scenario "The default Loki" and the test `test_a_call_with_no_url_queries_the_default_loki` hold it. The kubectl fallback in `execute_logql_query` serves a person with no Loki.
- **The egress level stays private**: The Loki client is internal infrastructure (README, SSRF protections). A host that answers a loopback or private address is dialled, whatever `ai.allow_private_network` says. A host that answers cloud metadata is refused. A person writes `loki.url` (`config set`, the config file or the variable), and the MCP exposure table holds no `config set`, so a model cannot change it. A call that gives `loki_url` still fails, also when the setting is set.
- **The MODIFIED requirement keeps the definition by reference**: "The default Loki" stays "what `devops k8s logs` queries with no `--loki-url`". The text now says what that is, and the scenario "The default Loki" now says `loki.url` is not set. A scenario for a set `loki.url` is new. The text is 492 characters, under the limit of 500.

## Rejected alternatives

- **Read the setting in the CLI command only (`cluster_context.py`)**: The MCP tool, the live log pane and the dry-run plan would keep `localhost` (callers in `ui/widgets.py:211` and `cluster_plans.py:112`). The review of this plan found the dry-run mismatch.
- **Stop with an error when `--loki-url` and `loki.url` are both absent**: The issue allows it, but the criterion "default unchanged" and the spec scenario "The default Loki" (`openspec/specs/k8s-logs/spec.md`) keep `localhost:3100`. The error would also remove the kubectl fallback for a person with no Loki.
- **`ServiceUrlStr` for `loki.url`**: It accepts `k8s://` values that the Loki client cannot dial (see the second decision).
- **A new file for the Loki settings**: One field does not need a file; `settings.py` holds every section.
- **Write `loki.url` in `devops k8s configure-urls`**: The spec `cluster-service-addressing` names the six keys that command writes. A change to that list is a separate topic and needs its own issue.
