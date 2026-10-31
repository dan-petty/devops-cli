# Tasks

## 1. Tests First (TDD) and Factory Transport Parameter

Reads: None.. Changes: None..

- [x] 1.1 Add failing tests for kept pre-flight callers and AI client base URL in `tests/http/test_http_egress.py`, and verify fail-to-pass
- [x] 1.2 Add `transport` parameter to `new_http_client` and `new_async_http_client` in `src/devops_cli/http/client.py`
- [x] 1.3 Update `src/devops_cli/ai/client/base.py` to use `new_http_client` with injected transport

## 2. Rewire Kept Pre-Flight Callers and Remove Pre-Flight Paths

Reads: None.. Changes: None..

- [x] 2.1 Update `src/devops_cli/ai/rag/qdrant.py` to use `vet_addresses` and document time-of-check gap
- [x] 2.2 Update `src/devops_cli/commands/k8s/cluster_context.py` to use `vet_addresses` and document time-of-check gap
- [x] 2.3 Update `src/devops_cli/docker/engine.py` to use `vet_addresses` and document time-of-check gap
- [x] 2.4 Update `src/devops_cli/commands/config.py` wizard to use `vet_addresses` at configured level and document time-of-check gap
- [x] 2.5 Remove pre-flight checks and `validate_configured_service_url` call in `src/devops_cli/ai/client/network.py`
- [x] 2.6 Delete `_resolve_host_ips`, `_enforce_non_private_ssrf`, and unused validators in `src/devops_cli/core/validation.py`, `src/devops_cli/http/validation.py`, and `src/devops_cli/http/__init__.py`

## 3. ast-grep Rules and Tests

Reads: None.. Changes: None..

- [x] 3.1 Add ast-grep rules `net-raw-http-client.yml` and `net-pre-flight-resolve.yml` in `.ast-grep/rules/`
- [x] 3.2 Add rule tests in `.ast-grep/rule-tests/` and verify `uv run ast-grep test --skip-snapshot-tests` passes

## 4. Test Suite and Documentation Updates

Reads: None.. Changes: None..

- [x] 4.1 Update tests in `tests/` that reference deleted validation functions to use `ScriptedResolver` or updated APIs
- [x] 4.2 Update documentation in `README.md`, `ARCHITECTURE.md`, `SECURITY.md`, `docs/ROUTINE_TASKS.md`, `docs/KNOWN_ISSUES.md`, and the knowledge base
- [x] 4.3 Run `uv run devops docs generate --sync-readme` and verify `uv run devops ci` passes
