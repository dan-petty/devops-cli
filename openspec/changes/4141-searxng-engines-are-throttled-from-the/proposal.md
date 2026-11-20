# Proposal

## Why

#4141 reports that the pinned SearXNG in namespace `devops` returns few hits or none, and that the chain then falls through to `ddgs` and Firecrawl. The 3-hour log of 2026-11-08 records HTTP 400 from `api.stackexchange.com` for `stackoverflow`, `askubuntu` and `superuser` with no key in the request, a 180 s suspension of the same three for too many requests, and no hit from them; the log holds no reply body, so the cause of the 400 is not proven. The change removes the three from `keep_only` and makes `devops k8s searxng-check` fail a reply that names one, so the engine set starts from engines that answer while the measure of #4201 chooses the rest.

## What Changes

- Add `stackoverflow`, `askubuntu` and `superuser` to `src/devops_cli/k8s/searxng_check.py:70:OFF_ENGINES: Final = ("brave", "braveapi", "google", "bing", "startpage", "mojeek", "qwant")`, so the live check fails a reply that names one.
- Update `tests/k8s/test_searxng_check.py:55:assert sorted(OFF_ENGINES) == sorted(` to the ten names and add a case for a Stack Exchange engine that must stay off.
- Remove the three names from the list under `k8s/devops/searxng/configmap.yaml:30:keep_only:`, so the settings keep `duckduckgo`, `wikipedia`, `github`, `arxiv`, `mdn` and `docker hub`, and record the log facts in the header comment.
- Rewrite the engines bullet `docs/CLUSTER.md:243:- **The engines.**` to name the six kept engines and to record the HTTP 400 without a key, the unproven cause and the absent retry loop.
- Add no test over the ConfigMap: `docs/TESTING.md:68:and never a test that reads the file (#6080)` refuses it, and the engine set is proven by the live check and its offline case.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `searxng-service`: The settings keep only keyless engines

## Impact

- Code: `src/devops_cli/k8s/searxng_check.py`, `k8s/devops/searxng/configmap.yaml`
- Documents: `docs/CLUSTER.md`
- Tests: `tests/k8s/test_searxng_check.py`, `tests/commands/k8s/test_k8s_devops_stack.py`

## Feasibility

- `probes` confirms the cited settings path word for word: "The path `k8s/devops/searxng/configmap.yaml` is a file of the staging commit."
- `read_file` of `k8s/devops/searxng/configmap.yaml` lines 26 to 42 showed the nine names under `k8s/devops/searxng/configmap.yaml:30:keep_only:`, at lines 31 to 39, and each member has a decision: `duckduckgo`, `wikipedia`, `github`, `arxiv`, `mdn` and `docker hub` stay, and `stackoverflow`, `askubuntu` and `superuser` leave.
- `read_file` of the same file, lines 1 to 4, showed `k8s/devops/searxng/configmap.yaml:2:no secret:`, so the settings hold no key of an engine.
- `read_spec` of `searxng-service` returned the requirement `The settings keep only keyless engines`, whose text names the nine engines and whose one scenario is `A suspended engine is kept`, so the change modifies that requirement and keeps its scenario.
- `search_code` for `keep_only` returned no hit under `src/` or `tests/`, and its hits are `k8s/devops/searxng/configmap.yaml:30:keep_only:` and `docs/CLUSTER.md:243:- **The engines.**`, so no test asserts the engine list and the cluster document is the one list of the engines.
- `search_code` for `stackoverflow` returned `docs/CLUSTER.md:243:- **The engines.**`, `k8s/devops/searxng/configmap.yaml:34:- stackoverflow`, the archived changes, and the saved reply `tests/fixtures/searxng/search_reply.json:99:"stackoverflow",`, which the provider test reads as a reply body and never compares with the engine set; `k8s/README.md` holds no engine list.
- `read_file` lines 57 to 80 showed the staged tuple `src/devops_cli/k8s/searxng_check.py:70:OFF_ENGINES: Final = ("brave", "braveapi", "google", "bing", "startpage", "mojeek", "qwant")` with the comment above it, and `file_symbols` showed `src/devops_cli/k8s/searxng_check.py:def reply_problems` at line 146, so group 1 extends an existing constant and an existing function.
- `file_symbols` showed `src/devops_cli/k8s/searxng_check.py:def search_specs` at line 128, so the six rows of the live check, the `general` row included, exist and the new case holds the engine guard offline.
- `read_file` of `tests/k8s/test_searxng_check.py` lines 50 to 60 showed `tests/k8s/test_searxng_check.py:55:assert sorted(OFF_ENGINES) == sorted(`, the seven names at line 56, and lines 107 to 129 hold the engine cases with `duckduckgo` as the kept engine, so the module needs the tuple update and one new case and no other change.
- The issue records the `general` clause as already measured: "`devops k8s searxng-check` (PR #4136) got 1 hit for the plain `general` category while DuckDuckGo was CAPTCHA-blocked, 50 hits for `it` and 10 for `science`."
- The plan claims no cause of the HTTP 400: the issue states "The reply body is not in the log, so the cause of the 400 is not proven." and records "`superuser`, `stackoverflow`, `askubuntu` and `arxiv`: \"Too many request (suspended_time=180)\".", so the three leave for the recorded HTTP 400 and the no-hit reply with no key.
- `read_file` showed `src/devops_cli/ai/web_search.py:339:for provider in iter_configured_providers(settings):`, one pass over the configured providers with no second attempt, so a failed provider passes the search on with no retry and no wait.
- The ConfigMap test that the issue offers as its example is refused by the tree: `docs/TESTING.md:68:and never a test that reads the file (#6080)` states the rule, and `tests/invariants/test_k8s_searxng.py:5:No test asserts a value of the manifests (#6060).` holds it, so the criterion is delivered by the live check and its offline case, which the criterion allows with the words "A command or test that fails today".
- The refine comment of 2026-11-09 records "Moved to new items: #4201.", so the 3-day measure, the split between query rate and egress address, and the engine set beyond the three Stack Exchange engines stay with that item.
- The plan calls no function whose arguments need a checkout, a client or a network: `reply_problems` is a pure function of a status and a body, and the groups change files only.
- The plan introduces no verify program and no new failure class: `uv run devops ci test tests/k8s/test_searxng_check.py` runs `pytest` from the image, `uv run devops ci --check --only k8s` runs `kubectl` from the image, and `uv run devops ci docs` runs `devops` from the image, each with a checkout of the repository, no client and no network.
- The pod keeps `readOnlyRootFilesystem: true`, `runAsNonRoot: true` and `capabilities.drop: ALL`, and none of the three rows needs a program outside the image.
- The live check `uv run devops k8s searxng-check` needs a checkout of the repository, a client of the Kubernetes API and a network to the cluster, so it is `NOT_IN_RUNNER`: the runner pod holds no Kubernetes token, and a person runs it after the rollout.
- First checks against the real system, each with its command: `uv run devops ci test tests/k8s/test_searxng_check.py` fails before group 1 with the seven-name tuple; `uv run devops ci --check --only k8s` renders the ConfigMap after group 2; `uv run devops k8s searxng-check` passes after the rollout, with a hit in the `general` row.

## Existing Tool Considered

SearXNG (`searxng/searxng`, AGPL-3.0, maintained) already runs as the search backend and holds the whole change in its own settings: the engine allow-list through `engines.keep_only`. The change edits one ConfigMap, one live check and one document, and builds no code of its own.

## Dependencies

- The metric `devops_cli_web_searches_total` also appears in `docs/CLUSTER.md`, `docs/TELEMETRY.md`, `k8s/devops/monitoring/prometheus-rules-values.yaml`, `src/devops_cli/ai/web_search.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/telemetry/instruments.py`, `openspec/specs/web-search/spec.md`, `openspec/specs/roadmap-alternatives/spec.md`, `openspec/specs/roadmap-service-alerts/spec.md`, `tests/ai/test_web_search.py`, `tests/fixtures/prometheus_rules/crawl4ai_tests.yaml`, `tests/fixtures/prometheus_rules/roadmap_service_activity_hourly_tests.yaml`, `tests/fixtures/prometheus_rules/roadmap_service_activity_tests.yaml` and the archived changes; this change adds no instrument and no label, and the `docs/CLUSTER.md` line that describes the metric stays as it is.
