# Tasks

## 1. Loki query passthrough and egress enforcement

- [x] 1.1 Add failing unit tests verifying that Loki queries send the raw query string and since duration unchanged and use the egress factory (`uv run devops ci test tests/test_k8s_logql.py`).
- [x] 1.2 Update `execute_loki_query` to send raw query, since parameter, and execute via `new_http_client(level=EgressLevel.PRIVATE)`, deleting `_parse_duration_to_seconds` and its obsolete test (`uv run devops ci test tests/test_k8s_logql.py`).
- [x] 1.3 Regenerate documentation with `uv run devops docs generate --sync-readme`.

## 2. Namespace selector validation

- [x] 2.1 Add failing unit tests asserting that `--namespace` fails before sending any request when the query lacks the namespace or conflicts with it, suggesting the selector to use, and does not rewrite the query (`uv run devops ci test tests/test_k8s_logql.py`).
- [x] 2.2 Update `execute_logql_query` to validate namespace presence without query rewriting, raising `KubernetesLoggingError` with suggested selector on missing namespace (`uv run devops ci test tests/test_k8s_logql.py`).
- [x] 2.3 Regenerate documentation with `uv run devops docs generate --sync-readme`.

## 3. Kubectl fallback restrictions and execution

- [x] 3.1 Add failing unit tests asserting that fallback executes `kubectl logs -l <selector>` for equality selectors and `|=` line filters, and refuses regex matchers, `!=` matchers, label filters, and `| json` with an error citing `loki.url` (`uv run devops ci test tests/test_k8s_logql.py`).
- [x] 3.2 Update `execute_kubectl_logql` to execute `kubectl logs -l <selector>`, validate fallback query restrictions, reject unsupported queries naming `loki.url`, and remove obsolete `_get_matching_pods` (`uv run devops ci test tests/test_k8s_logql.py`).
- [x] 3.3 Regenerate documentation with `uv run devops docs generate --sync-readme`.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
