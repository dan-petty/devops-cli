# Task: URL and host:port reads use the sending client's parser (#1112)

**Issue**: [#1112](https://github.com/dan-petty/devops-cli/issues/1112)
**Status**: Done
**Milestone**: v0.2.32
**Priority**: priority/p2-medium
**Scope**: scope/security

## Description
Several modules read URLs or bare `host:port` pairs using ad-hoc substring tests, scheme sniffing (`"://"`), manual port tables (`443 if https else 80`), hand-rolled `split(":")` splits, and `str.replace` chains before handing the values to underlying clients (`httpx2`, `OTLPSpanExporter`, `socket`). When the custom parsing logic disagreed with the sending client, security boundaries broke: checks evaluated against one host while requests dialled another (e.g. `https://example.com\@192.0.2.1/v1`), valid IPv6 or IDN endpoints were rejected, and scheme-less credentials were sent over plaintext HTTP.

This fix unifies URL, authority, and model spec parsing around sending client parsers:
1. Created `devops_cli.http.urls` providing:
   - `get_url_origin(value)`: Resolves canonical `httpx2.Origin` or `None` without raising.
   - `read_url_or_authority(s)`: Parses standard URLs or bare authorities (`host[:port]`) into a `SplitResult` with a valid host, supporting bare and bracketed IPv6.
   - `extract_domain_target(s)`: Extracts the canonical domain or hostname.
   - `append_path(base, reference)`: Appends relative paths without dropping trailing slashes or path prefixes.
2. Centralized `model@endpoint` parsing into `devops_cli.ai.benchmark.model_spec`:
   - `parse_model_spec(entry)` cleanly splits `(model, endpoint)` preserving userinfo.
   - `parse_model_list(model_str)` splits comma-separated model strings.
   - Removed `CONST_MODEL_ENDPOINT_MARKERS` and ad-hoc splits.
3. Hardened key trust, crawler, probe, and credentials paths:
   - Benchmark runner key trust (`_key_for_endpoint`) checks canonical origin equality against configured endpoints via `get_url_origin`.
   - Docs ingester normalizes link resolution and origin checks via `httpx2.URL.origin`, sanitizes directory slugs, and prevents path traversal escapes.
   - Network probe (`_parse_target_endpoint`) returns `httpx2.Origin` and raises `ValidationError` for missing hosts or invalid ports.
   - OTLP telemetry exporter preserves user endpoints and derives `insecure` flag from scheme.
   - ArgoCD, Grafana, and Ollama settings refuse scheme-less URLs with `ConfigurationError`.
   - Vault broker URI parsing handles case-insensitive `vault://` schemes and preserves fragment separation.

## Key Changes
- **URL & Origin Utilities** (`src/devops_cli/http/urls.py`):
  - Implemented `get_url_origin`, `read_url_or_authority`, `extract_domain_target`, and `append_path`.
- **Model Spec Centralization** (`src/devops_cli/ai/benchmark/model_spec.py`):
  - Implemented `parse_model_spec` and `parse_model_list`.
  - Replaced manual splits in `runner.py`, `embedding_runner.py`, `benchmark.py`, and `server.py`.
- **Key Trust & Benchmark Runner** (`src/devops_cli/ai/benchmark/runner.py` & `embedding_runner.py`):
  - Used `get_url_origin` to match origins across configured base URLs and endpoints.
  - Required `--provider` when benchmark endpoint does not match configured `gateway_url` under gateway provider.
- **Docs Ingester Hardening** (`src/devops_cli/ai/library/docs_ingester.py`):
  - Replaced `netloc`, `urljoin`, and `urlparse` with `httpx2.URL` and `httpx2.Origin` comparisons.
  - Sanitized directory slugs to prevent traversal via `%2e%2e` and stripped userinfo.
- **Probe & Telemetry** (`src/devops_cli/sandbox/probe.py`, `src/devops_cli/telemetry/tracer.py`, `src/devops_cli/sandbox/metrics.py`):
  - `_parse_target_endpoint` returns `httpx2.Origin` and validates host and port.
  - `_build_scrape_url` parses target via `read_url_or_authority` and constructs valid `httpx2.URL`.
  - OTLP trace exporter passes unmodified endpoint and sets `insecure` from scheme.
- **Settings & Credentials** (`src/devops_cli/k8s/credentials.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/ai/models/ollama.py`):
  - `_clean_service_base_url` and `get_ollama_urls` refuse scheme-less entries with `ConfigurationError`.
- **Tests**:
  - Added key trust test cases for backslash host mismatch, default https ports, IDN punycode, and unparseable URLs in `tests/test_ai_benchmark.py`.
  - Added crawler origin filtering and slug traversal tests in `tests/test_docs_ingester.py`.
  - Added probe origin return and validation tests in `tests/test_sandbox_probe.py`.
  - Added telemetry OTLPSpanExporter and connection probe tests in `tests/test_telemetry.py`.
  - Added service credential scheme-less validation tests in `tests/test_k8s_credentials.py`.
  - Added Ollama URL normalization tests in `tests/test_ai_client_security.py`.
  - Added scrape URL construction tests in `tests/test_sandbox_metrics.py`.
  - Added whitelist host extraction and rejection tests in `tests/test_sandbox_policy_properties.py`.
  - Added Vault URI scheme-casing tests in `tests/test_vault_broker.py`.
  - Added MCP model string acceptance and rejection tests in `tests/test_mcp.py`.
  - Added embedding provider resolution tests in `tests/test_embedding_benchmark.py`.

## Acceptance Criteria
- [x] Key trust tests verify backslash mismatches fail closed, IDN origins match, and unparseable URLs return empty keys without raising.
- [x] Direct calls to `_key_for_endpoint` fail closed on malformed URLs.
- [x] Docs ingester follows links on same origin, skips scheme downgrades and invalid URLs, and confines directory slugs to children of the ingest root.
- [x] Network probe `_parse_target_endpoint` returns `httpx2.Origin` with scheme, host, and port, and raises `ValidationError` on malformed targets.
- [x] OTLP telemetry client preserves endpoints, dials correct host/port, and infers protocol from port 4317.
- [x] Credentials minting refuses scheme-less `argocd.url` and `grafana.url` with `ConfigurationError`.
- [x] `get_ollama_urls` normalizes uppercase schemes and refuses scheme-less URLs.
- [x] `_build_scrape_url` preserves target paths and handles hosts starting with "http".
- [x] Sandbox whitelist host extraction normalizes case and rejects empty port entries.
- [x] Vault broker parses uppercase `VAULT://` URIs.
- [x] MCP tools reject endpoint overrides (`x@...`) and accept valid multi-model specs.
- [x] Embedding runner selects provider based on origin matching or refuses unknown endpoints under gateway provider.
- [x] No forbidden parsing constructs remain across modified files.
- [x] All automated tests pass offline without external network dependencies.
