# Proposal

## Why

#2437 is the fifth and final part of #1381. Parts 1 to 4 moved HTTP clients to the egress-checked factory.
Two pre-flight resolve paths remain in `core/validation.py`: `_resolve_host_ips` and `_enforce_non_private_ssrf`.
They resolve a host name before the dial, and the dialler resolves it again.
This double-resolution creates a DNS-rebinding window.
This change deletes the pre-flight resolve paths.
The four kept pre-flight checks move to `vet_addresses`.
The last raw httpx2 clients in `ai/client/base.py` move to the factory.
Two ast-grep rules prevent regression.
The documents are updated to state that every HTTP client is checked at the connect.

## What Changes

- Delete `_resolve_host_ips`, `_enforce_non_private_ssrf`, `validate_url_egress`, `validate_url`, `validate_service_url`, and `validate_configured_service_url` in `src/devops_cli/core/validation.py`.
- Remove `resolve_dns` parameters from `is_cloud_metadata_host` and `is_loopback_or_private_host`.
- Remove deleted validator re-exports from `src/devops_cli/http/validation.py` and `src/devops_cli/http/__init__.py`.
- Rewire the four kept pre-flight callers to `vet_addresses` at their level: Qdrant (`ai/rag/qdrant.py`), manifest URL apply (`commands/k8s/cluster_context.py`), container engine endpoint (`docker/engine.py`), and the config init wizard (`commands/config.py`).
- Add a `transport` parameter to `new_http_client` and `new_async_http_client` in `http/client.py`.
- Rewire `ai/client/base.py` to build its clients via `new_http_client` instead of calling `httpx2.Client` directly.
- Remove pre-flight check in `validate_base_url` in `src/devops_cli/ai/client/network.py`.
- Add ast-grep rules `net-raw-http-client` and `net-pre-flight-resolve` in `.ast-grep/rules/` with rule tests in `.ast-grep/rule-tests/`.
- Update tests to use `ScriptedResolver` instead of patching `_resolve_host_ips`.
- Update documentation in `README.md`, `ARCHITECTURE.md`, `SECURITY.md`, `docs/ROUTINE_TASKS.md`, `docs/KNOWN_ISSUES.md`, and the knowledge base.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `configured-service-urls`: Connect-time checking replaces pre-flight resolution, kept pre-flight checks call vet_addresses, config init wizard admits loopback at configured level.

## Impact

- All HTTP connections are verified at connect time.
- Pre-flight DNS resolution paths are removed, closing the DNS rebinding window.

## Feasibility

- `rg -n '_resolve_host_ips|_enforce_non_private_ssrf' src` shows definitions and call sites in `core/validation.py`.
- `rg -n 'httpx2\.((Async)?Client|get|post)' src` confirms raw client construction remains only in `ai/client/base.py` and `http/client.py`.
- Dependencies #2422, #2424, #2430, #2431, #1319, and #1110 are closed and merged on `origin/main`.
- First checks run: `uv run devops ci test tests/http/test_http_egress.py` and `uv run ast-grep test --skip-snapshot-tests`.

## Existing Tool Considered

The egress checking is covered by `devops_cli.http.egress` (`vet_addresses`), already present in the codebase.
Static analysis is covered by `ast-grep`, already integrated in `.pre-commit-config.yaml`.
No new third-party library is needed.
