# Design

## Context

`src/devops_cli/k8s/logql.py` implements LogQL execution and Kubernetes log retrieval. See `proposal.md` for motivation.

## Goals / Non-Goals

**Goals:**
- Send queries to Loki unchanged, forwarding `since`, `limit`, and `direction` as URL query parameters.
- Route Loki requests through `devops_cli.http.client.new_http_client(level=EgressLevel.PRIVATE)`.
- Enforce that `--namespace` matches the stream selector. Reject queries missing the namespace with the suggested selector.
- Constrain the kubectl fallback strictly to `label="value"` matchers and `|=` line filters.
- Run `kubectl logs` with `-l <selector>` directly in fallback mode.
- Reject unsupported fallback queries with a clear error pointing to `loki.url`.

**Non-Goals:**
- Building a full LogQL parser or pipeline evaluator in Python.
- Supporting regex line filters or pipeline stages in kubectl fallback mode.

## Decisions

### 1. Byte-for-byte query transmission to Loki
The raw query provided by the user is passed directly to Loki's `/loki/api/v1/query_range` endpoint without modification.
- *Rationale*: Loki possesses the authoritative parser and evaluator for LogQL. DevOps CLI must not rewrite queries or strip valid matchers.
- *Rejected Alternative*: Reconstruct the query from an abstract syntax tree. *Evidence*: The previous AST serializer dropped regex matchers (`=~`), dropped line filters, and failed to escape filter strings properly.

### 2. Upstream parameter forwarding for duration and limits
Remove `_parse_duration_to_seconds`. Forward `since` directly to Loki and kubectl.
- *Rationale*: Loki natively accepts Prometheus-style durations in `since`. Kubectl also natively parses `--since`. Hand-rolled parsing broke composite durations like `1h30m`.
- *Rejected Alternative*: Parse duration with `dateutil` or `pytimeparse`. *Evidence*: Loki and kubectl already parse duration strings natively. Retaining parsing code in devops-cli violates rule 3 of AGENTS.md.

### 3. Namespace validation instead of query rewriting
When the user specifies `--namespace`, verify that `parsed.selectors.get("namespace") == namespace`. If the selector lacks a namespace, raise `KubernetesLoggingError` with the recommended selector.
- *Rationale*: Preserves byte-for-byte query fidelity while preventing unintentional cross-namespace queries.
- *Rejected Alternative*: Inject `namespace="<ns>"` into the user's raw query string. *Evidence*: Query string injection breaks complex LogQL pipeline formatting and drops regex stream selectors.

### 4. Direct `kubectl logs -l` execution and strict capability gating in fallback
In fallback mode, validate that the query contains only `label="value"` stream selectors and `|=` substring filters. Refuse anything else with `KubernetesLoggingError` citing `loki.url`. Run `kubectl logs -n <ns> -l <selectors> --tail=<limit>`. Apply `|=` filters on stdout lines.
- *Rationale*: Aligns fallback capabilities strictly with what `kubectl` can evaluate. Eliminates the partial pod discovery loop.
- *Rejected Alternative*: Emulate LogQL JSON parsing and regex matching in Python. *Evidence*: Emulating pipelines in Python resulted in partial evaluation, silent omission of selectors, and unvetted pod selection (#1431).

### 5. Connect-time egress enforcement
Instantiate the HTTP client via `new_http_client(level=EgressLevel.PRIVATE, timeout=10.0)`.
- *Rationale*: Ensures cluster requests obey SSRF protections and deny cloud metadata access.
- *Rejected Alternative*: Use bare `httpx2.get`. *Evidence*: Bypassed connection vetting and allowed SSRF risks (#1314).

## Risks / Trade-offs

- [Risk] Users with complex LogQL queries running against clusters without Loki will see errors instead of partial fallback logs. → Mitigation: Error message explicitly instructs configuring `loki.url` to evaluate full LogQL queries.
