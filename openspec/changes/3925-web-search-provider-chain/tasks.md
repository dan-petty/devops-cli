# Tasks

## 1. Search the web through a chain of providers

Reads: `src/devops_cli/ai/common_tools.py`, `src/devops_cli/roadmap/refine_investigation.py`, `src/devops_cli/roadmap/refine.py`, `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/telemetry/instruments.py`, `tests/ai/test_common_tools.py`. Changes: `src/devops_cli/ai/web_search.py`, `src/devops_cli/ai/common_tools.py`, `src/devops_cli/roadmap/refine_investigation.py`, `src/devops_cli/roadmap/refine.py`, `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/exceptions/ai.py`, `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/lang/en/messages.py`, `tests/ai/test_web_search.py`, `tests/ai/test_common_tools.py`, `tests/http/test_http_egress.py`, `tests/roadmap/test_roadmap_alternatives.py`, `tests/roadmap/test_roadmap_refine.py`, `tests/roadmap/test_roadmap_refine_investigation.py`, `tests/roadmap/test_roadmap_stage_tools.py`, `tests/roadmap/test_roadmap_dry_runs.py`.

- [x] 1.1 In `tests/ai/test_web_search.py`, write the cases of the chain: the first provider with a hit answers, each refusal and a timeout pass the search on and count, a healthy empty reply passes on, every provider failing raises `SearchFailed`, one empty answer with the rest failed returns an empty list, an unconfigured provider is skipped and not counted, the deadline, the dedup and the scheme filter, each refused query, and the log line of a failed attempt
  - Verification: `uv run devops ci test tests/ai/test_web_search.py`
- [x] 1.2 In `src/devops_cli/ai/web_search.py`, add `web_search`, `SearchHit`, `SearchProvider`, `DuckDuckGoProvider` and `FirecrawlProvider` (moved from `common_tools.py`), the query guard, the counter `WEB_SEARCHES_TOTAL`, the exceptions `SearchFailed` and `SearchQueryRefused`, the section `search` of the settings and the constants. Delete `src/devops_cli/ai/common_tools.py`, `tests/ai/test_common_tools.py` and the two old instruments
  - Verification: `uv run devops ci test tests/ai/test_web_search.py tests/http/test_http_egress.py tests/config`
- [x] 1.3 Make `cited_web_search`, `InvestigationTools`, `AlternativesTools`, `WebSearch`, `web_search_of` and `request_plan.py` use the chain with no key argument, and update the tests of the roadmap jobs
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_alternatives.py tests/roadmap/test_roadmap_refine.py tests/roadmap/test_roadmap_refine_investigation.py tests/roadmap/test_roadmap_stage_tools.py tests/roadmap/test_roadmap_dry_runs.py`

## 2. Rename the alerts and update the documents

Reads: `k8s/monitoring/prometheus-values.yaml`, `tests/fixtures/prometheus_rules/roadmap_service_activity_tests.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `k8s/README.md`, `docs/roadmap/alternatives.md`, `docs/roadmap/refine.md`. Changes: `k8s/monitoring/prometheus-values.yaml`, `tests/fixtures/prometheus_rules/roadmap_service_activity_tests.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `k8s/README.md`, `docs/roadmap/alternatives.md`, `docs/roadmap/refine.md`, `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`, `docs/ERRORS.md`, `docs/TELEMETRY.md`.

- [x] 2.1 Rename `RoadmapServiceFirecrawlRefused` to `RoadmapServiceWebSearchRefused` (by `backend` and `result`), point `RoadmapServiceAlternativesNotSearching` at `devops_cli_web_searches_total`, and update their rule tests and the promtool fixture
  - Verification: `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py`
- [x] 2.2 Update `k8s/README.md`, `docs/roadmap/alternatives.md` and `docs/roadmap/refine.md`, and regenerate `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`, `docs/ERRORS.md` and `docs/TELEMETRY.md`
  - Verification: `uv run devops docs generate --sync-readme && git diff --exit-code docs README.md`
- [x] 2.3 Check that no file outside the archive of changes and the history holds the two old counter names
  - Verification: `! git grep -n -e devops_cli_firecrawl_searches_total -e devops_cli_web_search_fallbacks_total -- src tests/ai tests/http tests/prometheus tests/roadmap docs k8s`

## Criteria

- Group 1: `web_search` SHALL return the hits of the first provider with a hit and SHALL ask no later provider.
- Group 1: A provider that fails or returns no hit SHALL pass the search on with no retry and no wait.
- Group 1: `web_search` SHALL raise `SearchFailed` when no provider answered, and return an empty list when one answered empty and the rest failed.
- Group 1: The guard SHALL raise `SearchQueryRefused` and send no request for a secret, an e-mail address, a private address, an internal host name, a leading `!` and a query over the cap.
- Group 1: A failed attempt SHALL log the backend and the status or the error class, and SHALL NOT log the key or the query.
- Group 1: The dry run of `devops roadmap alternatives` SHALL make no request.
- Group 2: `RoadmapServiceWebSearchRefused` and `RoadmapServiceAlternativesNotSearching` SHALL read `devops_cli_web_searches_total`.
- Group 2: The generated documents SHALL list the section `search`, its variables and the counter.

## Workflow follow-up

- The provider `searxng` is the item #3927. It adds `search.searxng_url` and one class.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
