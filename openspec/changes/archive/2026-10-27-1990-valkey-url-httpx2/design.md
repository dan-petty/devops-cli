# Design

## Context

See proposal.md - Why.
`devops k8s configure-urls` discovers services in the cluster and configures their endpoint URLs. Detected NodePort and LoadBalancer URLs typically carry the `http://` scheme. For Valkey, `_as_valkey_url` transforms the detected URL into a `valkey://` URL, preserving host and port components and ensuring bracketed IPv6 formatting.

## Goals / Non-Goals

**Goals:**
- Defensively guard `_as_valkey_url` against invalid URL inputs or URLs without a host.
- Pin `_as_valkey_url` URL construction with unit tests covering IPv4, bracketed IPv6, localhost, and invalid URLs.
- Assert that obsolete predicates `_has_non_default_valkey_port` and `_should_update_valkey` remain deleted.
- Assert that no legacy `tcp://` or `"tcp"` scheme literals exist in `networking.py`, `ai_runs.py`, `run_store.py`, and `src/devops_cli/valkey/`.

**Non-Goals:**
- Modify `_update_valkey_url` or `_apply_service_url`, which already correctly preserve custom loopback ports and route updates.
- Re-introduce compatibility shims or legacy settings.

## Decisions

### Decision: Validate non-empty host in `_as_valkey_url` and catch `httpx2.InvalidURL, ValueError`

`_as_valkey_url` catches `(httpx2.InvalidURL, ValueError)` and verifies `address.host` is non-empty before constructing the `valkey://` URL. If invalid or empty, it returns `None`.

*Alternative rejected:* Let `httpx2.InvalidURL` bubble up. Rejected because service detection fallback helpers gracefully return `None` on unparseable URLs.

### Decision: Dedicated test coverage in `tests/test_k8s_networking.py`

Add targeted unit tests directly to `tests/test_k8s_networking.py` alongside the existing URL configuration tests.

## Risks / Trade-offs

- [Risk of malformed URLs causing crashes] → Mitigated by `try...except (httpx2.InvalidURL, ValueError)` guard and empty host check.
