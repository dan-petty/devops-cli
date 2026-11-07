# Tasks

## 1. Add the SearXNG provider

Reads: `src/devops_cli/ai/web_search.py`, `src/devops_cli/ai/page_text.py`, `src/devops_cli/http/egress.py`, `src/devops_cli/roadmap/request_plan.py`. Changes: `src/devops_cli/ai/web_search.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/telemetry/instruments.py`, `tests/ai/test_web_search_searxng.py`, `tests/fixtures/searxng/search_reply.json`, `tests/ai/test_web_search.py`, `tests/roadmap/test_roadmap_dry_runs.py`.

- [x] 1.1 In `tests/ai/test_web_search_searxng.py` and `tests/fixtures/searxng/search_reply.json`, write the cases of the provider: a good reply, the request parameters, the cap, each status, a redirect, an empty reply with and without an unresponsive engine, a reply that is not readable, the byte cap, no address, a loopback address, a cluster address with the flag off and on, a refused address, and the log line
  - Verification: `uv run devops ci test tests/ai/test_web_search_searxng.py`
- [x] 1.2 Add `SearxngProvider`, `method` on the providers, the setting `search.searxng_url`, the constants, and the `refused` count of a refused address in `web_search`; make the dry run use `provider.method`
  - Verification: `uv run devops ci test tests/ai/test_web_search.py tests/ai/test_web_search_searxng.py tests/roadmap/test_roadmap_dry_runs.py tests/config`

## 2. Update the documents

Reads: `k8s/README.md`, `k8s/devops/configmap.example.yaml`. Changes: `k8s/README.md`, `k8s/devops/configmap.example.yaml`, `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`, `docs/TELEMETRY.md`.

- [x] 2.1 Name the cluster address in the example ConfigMap and describe the provider in `k8s/README.md`, and regenerate the settings documents
  - Verification: `uv run devops docs generate --sync-readme && uv run devops docs generate --check`

## Criteria

- Group 1: The provider SHALL send `GET /search` with `format=json` and follow no redirect.
- Group 1: A status other than 200 SHALL count with the status as the result, and an empty result with an unresponsive engine SHALL count as `degraded`.
- Group 1: A loopback address SHALL need no flag, and a cluster address SHALL need `ai.allow_private_network`.
- Group 2: The generated documents SHALL list `search.searxng_url`.

## Workflow follow-up

- The SearXNG manifests are the item #3924. The live check of the pinned image is #3929: it replaces the fixture with a saved reply and checks the categories.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
