# Proposal

## Why

Issue #1990: `devops k8s configure-urls` previously risked writing `http://<node>:<port>` or `tcp://` for `valkey.url`, and wrote unbracketed IPv6 addresses in `valkey.host`. The core implementation was completed in commit `12fa20c2` (#2087) as part of #1113 step D, but #2087 closed #2060 and left #1990 open. This change hardens `_as_valkey_url` defensively against invalid URLs and missing hostnames and adds dedicated regression test coverage pinning all acceptance criteria of #1990.

## What Changes

- Harden `_as_valkey_url` in `src/devops_cli/commands/k8s/networking.py` to catch `httpx2.InvalidURL` and `ValueError` and ensure a non-empty hostname is present before formatting `valkey://`.
- Add unit tests in `tests/test_k8s_networking.py` verifying `_as_valkey_url` URL construction, bracket formatting for IPv6, and handling of malformed input.
- Add test assertions in `tests/test_k8s_networking.py` ensuring the obsolete predicates `_has_non_default_valkey_port` and `_should_update_valkey` remain removed.
- Add test assertions in `tests/test_k8s_networking.py` verifying acceptance criterion 5: no `tcp://` or `"tcp"` scheme literals remain in `networking.py`, `ai_runs.py`, `run_store.py`, or `src/devops_cli/valkey/`.

This change alters no behavior that an external consumer observes. The change sets `skip_specs: true` in `.openspec.yaml`.

This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/commands/k8s/networking.py`: Guard `_as_valkey_url` with exception handling and empty host validation.
- `tests/test_k8s_networking.py`: Dedicated unit tests for `_as_valkey_url`, removal of obsolete predicates, and verification of scheme cleanliness.

## Feasibility

The premise was verified against the real codebase and test suite:
- `httpx2.URL(scheme="valkey", host=..., port=...)` formats bracketed IPv6 addresses correctly (e.g. `valkey://[2001:db8::5]:30637`).
- `tests/test_k8s_networking.py` and `tests/test_k8s_proxy_addressing.py` pass offline.
- Subsystem scan confirms zero occurrences of `tcp://` or `"tcp"` scheme literals across `src/devops_cli/commands/k8s/networking.py`, `src/devops_cli/commands/ai_runs.py`, `src/devops_cli/ai/run_store.py`, and `src/devops_cli/valkey/`.

## Existing Tool Considered

`httpx2.URL` parses and constructs URLs with standard RFC-compliant IPv6 bracket formatting. `_apply_service_url` manages service URL configuration updates. Internal functions `_has_non_default_valkey_port` and `_should_update_valkey` were deleted.
