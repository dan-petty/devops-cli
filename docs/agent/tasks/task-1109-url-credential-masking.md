# Task: URL Credential Masking via Standard Library and HTTPX2 (#1109)

**Issue**: [#1109](https://github.com/dan-petty/devops-cli/issues/1109)
**Status**: Done
**Milestone**: v0.2.31
**Priority**: priority/p1-high
**Scope**: scope/security, scope/ai, scope/telemetry

## Description

Prior to this change, credentials embedded in URLs were masked using hand-written string manipulation across four distinct locations (`sanitizer.py`, `exceptions/security.py`, `server/routes/telemetry.py`, and `openai.py`). These approaches exhibited several critical failure modes:
1. `SSRFBlockedError` used `netloc.partition("@")`, which split at the first `@` rather than the last `@`, leaving userinfo credentials partially unmasked when passwords contained `@` (e.g., `user:pa@ss@example.com`), and raised uncaught `ValueError` on malformed port numbers (`http://169.254.169.254:abc/`).
2. `mask_uri_credentials` reconstructed URLs by formatting strings from `hostname`, dropping IPv6 brackets (`[2001:db8::1]`) and rendering resulting URLs unparseable.
3. `sanitize_telemetry_endpoint` dropped IPv6 brackets (`http://[::1]:4318` became `http://::1:4318`), failed to mask Carrier-Grade NAT addresses (`100.64.0.0/10`), used brittle string tuple checks for loopback, and introduced an unnecessary wrapper function (`_sanitize_telemetry_endpoint`) in routes.
4. `redact_text` only checked `http` and `https` schemes with a strict regex (`https?://[^:/\s@]+:[^@/\s?#]+@`), rewrote every matched `http://` URL to `https://`, and left non-HTTP schemes (`postgres://`, `redis://`, `mysql://`, `custom://`), empty-username URLs (`redis://:pw@...`), uppercase schemes (`HTTP://`), and passwords containing `#` or `/` unmasked.
5. `served_by` from LiteLLM's `x-litellm-model-api-base` header was stored directly without stripping userinfo credentials across spend ledgers, call observers, event payloads, and trace span attributes.
6. The HashiCorp Vault broker recorded raw `VAULT_ADDR` on trace span attributes and debug logs without masking embedded credentials.
7. Two callers (`argo/gitops.py` and `sandbox/metrics.py`) passed free-text exception strings into `mask_uri_credentials`.

To eliminate these vulnerabilities, standardize masking behaviors, and adhere to library-first principles:
1. Standardized single-URL credential masking (`mask_uri_credentials`) on `httpx2.URL`:
   - Fails closed to `<masked-url>` if `httpx2.InvalidURL` is raised or if the input contains `@` but `httpx2` finds no userinfo.
   - Preserves IPv6 brackets and masks passwords to `***` (`user:***@host` or `***@host` for empty usernames).
   - Preserves lone usernames (`custom://myuser@myhost/path`, `https://ghp_x@github.com/o/r`) without alteration per owner decision.
2. Refactored `SSRFBlockedError`:
   - Eliminates legacy `partition("@")` and `_replace(netloc=...)` string surgery.
   - Masks `target_url` using `mask_uri_credentials` before applying the 256-character bounding limit.
   - Formats human-readable display messages with literal `<masked>` host placeholder while preserving scheme, port, and path without percent-encoding.
   - Fails closed on invalid URLs to `SSRF blocked: <masked-url> ({reason})` with `details["target_url"]` set to `<masked-url>`.
3. Standardized free-text URL scanning and redaction in `redact_text`:
   - Locates candidate URLs via RFC 3986 scheme grammar capped at 32 characters with lookahead preventing quadratic backtracking (`CONST_URL_CANDIDATE_RE`).
   - Parses candidates strictly with `urllib.parse.urlsplit` (splitting userinfo at the last `@`).
   - Slices only the userinfo portion, replacing credentials with `<masked-user>:<masked-password>` while keeping scheme, host, port, and trailing path bytes exactly as written.
   - Fails closed to `<masked-url>` if candidate contains `@` and `urlsplit` raises or `.port` raises `ValueError`.
4. Refactored OTLP telemetry endpoint sanitization:
   - Eliminates the redundant `_sanitize_telemetry_endpoint` wrapper in `server/routes/telemetry.py`.
   - Strictly parses via `urlsplit` and classifies host IP addresses using `ipaddress` (`ip.is_global` and loopback checks).
   - Masks internal/private, CGNAT (`100.64.0.0/10`), link-local, and documentation IPs to URL-safe `internal-ip`.
   - Reconstructs clean URLs via `httpx2.URL` with brackets maintained and userinfo stripped.
5. Introduced centralized `extract_served_by` in `ai/client/network.py`:
   - Strips userinfo via `httpx2.URL(val).copy_with(userinfo=b"")`.
   - Preserves bare `host:port` endpoints and drops invalid or suspicious entries.
   - Updated blocking and streaming OpenAI-compat readers in `openai.py` to route through `extract_served_by`.
   - Confined references to `CONST_AI_GATEWAY_SERVED_BY_HEADER` and `x-litellm-model-api-base` strictly to `constants.py` and `network.py`.
6. Enforced credential masking on Vault spans in `vault_broker.py` using `mask_uri_credentials`.
7. Cleaned up call sites in `argo/gitops.py` and `sandbox/metrics.py` to invoke free-text sanitizers directly.

## Key Changes

- **Constants (`src/devops_cli/config/constants.py`)**:
  - Added `CONST_URL_CANDIDATE_RE` defining RFC 3986 capped scheme pattern with lookahead.
- **Universal Sanitizer (`src/devops_cli/security/sanitizer.py`)**:
  - Replaced legacy URL regex in `_SECRET_PATTERNS` with `(CONST_URL_CANDIDATE_RE, _mask_url_candidate)`.
  - Implemented `_mask_url_candidate` to splice userinfo via `urlsplit` with fail-closed `<masked-url>`.
  - Reimplemented `mask_uri_credentials` using `httpx2.URL` and `***` placeholder.
  - Reimplemented `sanitize_telemetry_endpoint` using `urlsplit`, `ipaddress`, and `httpx2.URL` with `internal-ip`.
- **Security Exceptions (`src/devops_cli/exceptions/security.py`)**:
  - Refactored `SSRFBlockedError` to eliminate `partition("@")` and `_replace(netloc=...)`, masking target URLs via `mask_uri_credentials` and formatting display messages safely.
- **AI Gateway Client (`src/devops_cli/ai/client/network.py`, `src/devops_cli/ai/client/openai.py`)**:
  - Implemented `extract_served_by` in `network.py` stripping userinfo via `httpx2.URL.copy_with(userinfo=b"")`.
  - Replaced direct header reads in `_openai_compat_messages` and `_openai_compat_stream` with `extract_served_by`.
  - Removed `CONST_AI_GATEWAY_SERVED_BY_HEADER` import from `openai.py`.
- **Vault Broker (`src/devops_cli/security/vault_broker.py`)**:
  - Masked `vault_addr` on `security.vault_broker.get_status` span attributes via `mask_uri_credentials`.
- **Call Sites & Server Routes (`src/devops_cli/argo/gitops.py`, `src/devops_cli/sandbox/metrics.py`, `src/devops_cli/server/routes/telemetry.py`, `src/devops_cli/exceptions/ai.py`)**:
  - Removed inner `mask_uri_credentials` from `argo/gitops.py` and `sandbox/metrics.py`.
  - Passed `gateway` directly to `mask_uri_credentials` in `exceptions/ai.py`.
  - Deleted pass-through wrapper `_sanitize_telemetry_endpoint` from `routes/telemetry.py`.
- **Test Suites (`tests/test_url_credential_masking.py`, `tests/test_consolidation_security_sanitizer.py`, `tests/test_exceptions.py`, `tests/test_subsystem_containment_and_redaction.py`, `tests/test_network_security_and_trace_correlation.py`)**:
  - Created `tests/test_url_credential_masking.py` verifying the full 25-row acceptance criteria table, Vault span masking, gateway served_by masking, execution speed benchmarks (< 1s for 100 KB fixtures), and architectural invariants.
  - Updated existing tests to check `internal-ip` and `user:***@`.

## Acceptance Criteria

- [x] Parametrized offline table test pins all 25 old and new masking behaviors across single URLs, SSRF targets, free text, and telemetry endpoints (`tests/test_url_credential_masking.py::test_acceptance_criteria_table`).
- [x] Passwords containing `@`, `#`, or `/` are masked properly, IPv6 host brackets remain intact, and non-HTTP schemes are covered.
- [x] `http://` URLs keep their scheme without being rewritten to `https://`.
- [x] Whole values that fail closed use the `<masked-url>` placeholder.
- [x] Internal, private, CGNAT (`100.64.0.0/10`), link-local, and documentation IPs in telemetry endpoints are masked to the `internal-ip` placeholder.
- [x] Userinfo is stripped from `served_by` across blocking and streaming paths (`test_gateway_served_by_blocking_and_streaming_strips_credentials`).
- [x] Only `config/constants.py` and `ai/client/network.py` reference `x-litellm-model-api-base` or `CONST_AI_GATEWAY_SERVED_BY_HEADER`.
- [x] Vault `get_status` span attribute `vault_addr` contains no credentials (`test_vault_broker_status_span_masks_credentials`).
- [x] Free-text URL masking runs in under 1.0 second across 100 KB fixtures (`test_free_text_masking_speed`).
- [x] Forbidden constructs (`_replace(netloc`, `partition("@")`, `https?://[^`, `://([^:]*)`) are completely eliminated from `exceptions/security.py` and `security/sanitizer.py` (`test_no_forbidden_constructs_remain`).
- [x] `mask_uri_credentials(str(` eliminated from `src/`.
- [x] `_sanitize_telemetry_endpoint` wrapper eliminated from `src/` and `tests/`.
- [x] `changelog.d/1109.md` records the change.
- [x] `uv run devops ci` passes.
