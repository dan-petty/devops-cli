# Tasks

## 1. Fall back to DuckDuckGo after a failed Firecrawl search

Reads: `src/devops_cli/ai/common_tools.py`, `src/devops_cli/roadmap/refine_investigation.py`, `src/devops_cli/telemetry/instruments.py`, `tests/ai/test_common_tools.py`, `tests/http/test_http_egress.py`, `openspec/specs/roadmap-refine/spec.md`. Changes: `src/devops_cli/ai/common_tools.py`, `src/devops_cli/roadmap/refine_investigation.py`, `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/config/defaults.py`, `tests/ai/test_common_tools.py`, `tests/http/test_http_egress.py`, `tests/roadmap/test_roadmap_dry_runs.py`, `pyproject.toml`, `uv.lock`.

- [x] 1.1 In `tests/ai/test_common_tools.py`, write the cases for `web_search`: Firecrawl refuses with HTTP 402 and DuckDuckGo results come back in the form of Firecrawl, Firecrawl answers and no fallback runs, both backends fail, the result limit, and the log line and the counter
  - Verification: `uv run devops ci test tests/ai/test_common_tools.py`
- [x] 1.2 In `src/devops_cli/ai/common_tools.py`, add `web_search` and `duckduckgo_search` with `ddgs==9.16.1` in `pyproject.toml` and `uv.lock`, the counter `WEB_SEARCH_FALLBACKS_TOTAL` in `src/devops_cli/telemetry/instruments.py`, and the constants and defaults. Make `cited_web_search` call `web_search`
  - Verification: `uv run devops ci test tests/ai/test_common_tools.py tests/roadmap/test_roadmap_refine_investigation.py tests/roadmap/test_roadmap_dry_runs.py`
- [x] 1.3 In `tests/http/test_http_egress.py`, add the caller `duckduckgo` at the public level
  - Verification: `uv run devops ci test tests/http/test_http_egress.py`

## 2. Document the fallback

Reads: `docs/TELEMETRY.md`, `k8s/README.md`, `docs/roadmap/alternatives.md`, `k8s/monitoring/prometheus-values.yaml`. Changes: `docs/TELEMETRY.md`, `k8s/README.md`, `docs/roadmap/alternatives.md`, `k8s/monitoring/prometheus-values.yaml`, `tests/fixtures/prometheus_rules/roadmap_service_activity_tests.yaml`.

- [x] 2.1 Name the fallback and the new counter in `k8s/README.md`, `docs/roadmap/alternatives.md` and `docs/TELEMETRY.md`, and change the text of the alert `RoadmapServiceFirecrawlRefused` in `k8s/monitoring/prometheus-values.yaml` and its test fixture
  - Verification: `uv run devops ci docs`

## Criteria

- Group 1: `web_search` SHALL search DuckDuckGo when the Firecrawl search raises an `httpx2.HTTPError` or a `ValueError`, and SHALL return results with `url`, `title` and `description`.
- Group 1: `web_search` SHALL NOT search DuckDuckGo after a search that Firecrawl answered.
- Group 1: The DuckDuckGo request SHALL go through `http_client` at the public level, and SHALL hold the query and no key.
- Group 1: The fallback SHALL add 1 to `devops_cli_web_search_fallbacks_total` by `backend` and `result`, and SHALL log one line that holds neither the key nor the query.
- Group 1: `web_search` SHALL raise an `httpx2.HTTPError` or a `ValueError` when both backends fail.
- Group 2: `docs/TELEMETRY.md`, `k8s/README.md` and `docs/roadmap/alternatives.md` SHALL name the fallback.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
