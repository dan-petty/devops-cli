# Proposal

## Why

DevOps CLI rewrote LogQL queries sent to Loki from a partial parser, which dropped matchers such as `=~` and label filters (#1431). The kubectl fallback emulated LogQL pipelines in Python, dropped non-equality matchers, and parsed durations with a custom helper that failed on valid duration strings.

This change fits one pull request.

## What Changes

- Send the user's LogQL query to Loki byte for byte, without query reconstruction.
- Pass `since`, `limit` and `direction` as direct parameters to the Loki `/loki/api/v1/query_range` endpoint.
- Require that `--namespace` matches the query selector's namespace. If the query lacks a namespace, fail before any request and print the suggested selector.
- Route Loki HTTP requests through the egress factory with `EgressLevel.PRIVATE`.
- Delete manual duration parsing helper `_parse_duration_to_seconds`.
- Restrict the kubectl fallback to `label="value"` matchers and `|=` substring filters.
- Run `kubectl logs` directly with `-l <selector>` instead of listing pods and reading them in a loop.
- Refuse unsupported fallback queries (regex matchers, `!=` matchers, label filters, pipelines such as `| json`) with an error naming `loki.url`.
- Delete LogQL pipeline emulation (`| json`, `| logfmt`, regex filters) in the fallback engine.

## Capabilities

### New Capabilities
- `k8s-logs`: LogQL cluster log streaming, Loki endpoint passthrough, and kubectl log fallback.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/k8s/logql.py`: LogQL query execution, Loki egress client, and kubectl fallback execution.
- `tests/test_k8s_logql.py`: Test suite updated with HTTP and process fakes for Loki passthrough and fallback validation.
- Obsolete functions `_parse_duration_to_seconds` and `_get_matching_pods` are removed.

## Feasibility

The premise was verified against the codebase and upstream tools:
- `src/devops_cli/k8s/logql.py` lines 35 and 152-182 drop non-equality matchers with `_SELECTOR_REGEX`.
- `src/devops_cli/k8s/logql.py` lines 431-438 reconstruct queries when `--namespace` is given.
- Loki HTTP API endpoint `/loki/api/v1/query_range` accepts `since`, `query`, `limit` and `direction` query parameters directly.
- `kubectl logs -l <selector>` is supported by Kubernetes 1.25+ and `kubectl` client tooling.
- `devops_cli.http.client.new_http_client` provides connect-time egress enforcement at `EgressLevel.PRIVATE`.

## Existing Tool Considered

Loki REST API and `kubectl logs` are the upstream tools covering cluster logging. DevOps CLI previously attempted to build a custom in-memory LogQL pipeline evaluator in Python (`evaluate_log_lines`, `extract_fields_json`, `extract_fields_logfmt`). Building and maintaining that custom LogQL engine in Python duplicates Loki's official engine. Replaced internal code includes custom duration parsing (`_parse_duration_to_seconds`), manual pod discovery (`_get_matching_pods`), and in-memory pipeline emulation in fallback mode.
