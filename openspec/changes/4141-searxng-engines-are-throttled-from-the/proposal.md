# Proposal

## Why

Issue #4141 reports that web search through the pinned SearXNG in namespace devops returns few hits or none, and the chain then falls through to ddgs and Firecrawl. The log of 2026-11-08 records stackoverflow, askubuntu and superuser suspended for too many requests and answering HTTP 400 from api.stackexchange.com with no key in the request, and the issue states that the cause of the 400 is not proven, so this change names no cause and claims no engine never answers. The settings still keep the three, so each it request spends one request on each of them, and devops k8s searxng-check cannot fail a settings regression that keeps one of them. The plan keeps duckduckgo, because the issue defers its removal to the measure under #4201, and adds no code for the throttle, which that measure covers.

## What Changes

- Add stackoverflow, askubuntu and superuser to the tuple `src/devops_cli/k8s/searxng_check.py:70:OFF_ENGINES: Final = ("brave", "braveapi", "google", "bing", "startpage", "mojeek", "qwant")`, so the tuple holds ten names and `devops k8s searxng-check` fails a reply that names one of the three.
- Update `tests/k8s/test_searxng_check.py`: the tuple assertion `tests/k8s/test_searxng_check.py:55:assert sorted(OFF_ENGINES) == sorted(` takes the ten names, the parametrized list `tests/k8s/test_searxng_check.py:108:"engine", ["google", "bing", "brave", "brave.news", "braveapi", "startpage", "mojeek", "qwant"]` gains the three, and `tests/k8s/test_searxng_check.py:118:def test_an_engine_that_stays_off_and_is_listed_as_unresponsive_is_a_problem() -> None:` gains a stackoverflow case, so the module fails on the base.
- Edit `k8s/devops/searxng/configmap.yaml`: remove the three Stack Exchange entries from the list under `keep_only` at line 30, so the list holds duckduckgo, wikipedia, github, arxiv, mdn and docker hub, and run `uv run devops k8s searxng-check` after the rollout, whose json-general row holds at least one hit.
- Record the log of 2026-11-08 in the header comment of `k8s/devops/searxng/configmap.yaml`, which starts at line 3: the HTTP 400 from api.stackexchange.com with no key in the request, the suspension for too many requests, and the fact that the cause of the 400 is not proven.
- Rewrite the engines bullet `docs/CLUSTER.md:243:keeps nine engines that need no key` and the off-engine list of `docs/CLUSTER.md:248:It fails a row when a reply lacks one of the seven keys`, so the document names the six kept engines, the ten engines that stay off and the log facts.
- Modify the requirement `The settings keep only keyless engines` of `searxng-service` and the requirement `Engines that stay off` of `k8s-searxng-check`, so the living specs hold the six kept engines and the ten-name tuple.
- Add no test over the ConfigMap, because `docs/TESTING.md:61:A test checks the source code of the project.` refuses one: the behavior test reads the `OFF_ENGINES` constant, and the live check with its offline cases proves the engine set.
- Keep duckduckgo and attribute the 1 hit of the general row on 2026-11-08 to no engine: the issue records that run as taken while DuckDuckGo was CAPTCHA-blocked, so the log names no engine for that hit, and the removal of duckduckgo waits on the measure under #4201.
- Add no retry loop, no engine key, no suspension value, no rate limit and no second general engine; the 3-day measure, the cause and the duckduckgo CAPTCHA stay with #4201.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `searxng-service`: The settings keep only keyless engines
- `k8s-searxng-check`: Engines that stay off

## Impact

- Code: `src/devops_cli/k8s/searxng_check.py`, `k8s/devops/searxng/configmap.yaml`
- Documents: `docs/CLUSTER.md`
- Tests: `tests/k8s/test_searxng_check.py`

## Feasibility

- `probes` confirms the cited settings path word for word: "The path `k8s/devops/searxng/configmap.yaml` is a file of the staging commit." `read_file` of the file showed `k8s/devops/searxng/configmap.yaml:30:keep_only:` with nine names at lines 31 to 39, so the premise of the issue holds at the staged commit.
- The fault of the earlier reply is corrected: the claim that duckduckgo is the only general engine that returns hits is gone, because the issue records that the check "got 1 hit for the plain `general` category while DuckDuckGo was CAPTCHA-blocked". `docs/CLUSTER.md:243:A request that names no category asks only the` names duckduckgo and wikipedia as the two general engines, and the log names no engine for that hit, so the plan claims none and keeps duckduckgo only because the issue defers its removal to the measure under #4201.
- The metric that the measure of the issue reads exists at the staged commit: `src/devops_cli/telemetry/instruments.py:258:WEB_SEARCHES_TOTAL = Instrument(` is the counter devops_cli_web_searches_total, and `src/devops_cli/telemetry/instruments.py:262:Web search attempts, by the provider that ran (the backend, or none) and the result: ok for a` gives its backend and result labels. This change adds no instrument and no label.
- The provider chain needs no change: `src/devops_cli/ai/web_search.py:5:passes the search on at once, with no retry and no wait` states that a failed provider passes the search on at once, so the decision of #4094 stays and this change edits no line of that module.
- The staged value of the constant that the plan changes: `src/devops_cli/k8s/searxng_check.py:70:OFF_ENGINES: Final = ("brave", "braveapi", "google", "bing", "startpage", "mojeek", "qwant")`, seven names, matched as a prefix by `src/devops_cli/k8s/searxng_check.py:def _off_engines`; the plan gives it ten names, so the count is 7 at the staged commit and 10 after the change.
- The count of the engine set and the decision for each member: `read_file` of `k8s/devops/searxng/configmap.yaml:30:keep_only:` counted nine names at lines 31 to 39. duckduckgo, wikipedia, github, arxiv, mdn and docker hub stay, and stackoverflow, askubuntu and superuser leave, so the list holds six after the change and no member is left undecided.
- `references` for `OFF_ENGINES` answered "files 3, lines 10": `src/devops_cli/k8s/searxng_check.py` and `tests/k8s/test_searxng_check.py`, both in group 1, and `openspec/changes/archive/2026-11-08-3929-searxng-check-command/tasks.md`, the record of a merged change.
- `references` for `stackoverflow` answered "files 12, lines 13". The files outside `openspec/changes/archive/` are `k8s/devops/searxng/configmap.yaml` (group 2), `docs/CLUSTER.md` (group 3), `openspec/specs/searxng-service/spec.md` (a design decision, because a task group never writes `openspec/specs/`) and `tests/fixtures/searxng/search_reply.json` (a design decision, left unchanged).
- `read_file` of `tests/k8s/test_searxng_check.py` showed the cases that the change turns red on the base: `tests/k8s/test_searxng_check.py:55:assert sorted(OFF_ENGINES) == sorted(`, the parametrized list `tests/k8s/test_searxng_check.py:108:"engine", ["google", "bing", "brave", "brave.news", "braveapi", "startpage", "mojeek", "qwant"]` and `tests/k8s/test_searxng_check.py:118:def test_an_engine_that_stays_off_and_is_listed_as_unresponsive_is_a_problem() -> None:`.
- The base specs that the delta replaces, from `read_spec`: `The settings keep only keyless engines` of `searxng-service` names the nine kept engines and one scenario, and `Engines that stay off` of `k8s-searxng-check` names the seven off engines and two scenarios. Both are `modified` with every scenario of the base, so no rule of a base requirement is lost.
- The general row of the live check: `src/devops_cli/k8s/searxng_check.py:def search_specs` builds one json-<category> row for each category of the provider, and `src/devops_cli/k8s/searxng_check.py:def reply_problems` fails a row with no hit, so a passing run is the run that the criterion asks for.
- The document lines that group 3 rewrites: `docs/CLUSTER.md:243:keeps nine engines that need no key` and `docs/CLUSTER.md:248:It fails a row when a reply lacks one of the seven keys` name the nine kept engines and the off engines today.
- The engine list is in `docs/CLUSTER.md` and not in `k8s/README.md`, so this change edits no line of `k8s/README.md`, the path that open pull request #6555 shares.
- No test reads the ConfigMap: `docs/TESTING.md:61:A test checks the source code of the project.` and `tests/invariants/test_k8s_searxng.py:5:No test asserts a value of the manifests (#6060).` state the rule, so the engine set is proven by the constant and by the live check.
- `uv run devops k8s searxng-check` needs a checkout of the repository, a client of the Kubernetes API and a network to the cluster: it forwards the service and starts throwaway pods through `src/devops_cli/k8s/searxng_check.py:def send_searches` and `src/devops_cli/k8s/searxng_check.py:def check_network_policy`, so it is NOT_IN_RUNNER and a person runs it after the rollout.
- No verify program is new: `uv run devops ci test tests/k8s/test_searxng_check.py` runs pytest from the image with failure class `test`; `uv run devops ci --check --only k8s` renders the manifests with the kubectl kustomize of the image with failure class `test`; and `uv run devops ci docs` runs devops from the image with failure class `test`. The pod keeps readOnlyRootFilesystem true, runAsNonRoot true, capabilities.drop ALL and allowPrivilegeEscalation false, and no row needs a program outside the image.
- First checks against the real system, each with its command: `uv run devops ci test tests/k8s/test_searxng_check.py` fails on the base on the ten-name tuple and on the three new engine cases; `uv run devops ci --check --only k8s` renders the ConfigMap after the settings group; `uv run devops ci docs` passes after the document group; and a person runs `uv run devops k8s searxng-check` after the rollout, whose json-general row holds a hit and whose reply names no engine that must stay off.
- The log facts of 2026-11-08, the CAPTCHA of duckduckgo, the suspension for too many requests and the HTTP 400 of api.stackexchange.com, are the issue's own record of the live pod: this run read no cluster and ran no command, so they are not checked here, and the plan names no cause for the 400.
- The measure and the cause stay with #4201, which the refine comment records as "Moved to new items: #4201." The plan adds no retry loop, as #4094 decided, and the provider chain stays as it is.

## Existing Tool Considered

SearXNG (`searxng/searxng`, AGPL-3.0, maintained) already runs as the search backend of the cluster, and its own settings hold the whole change: the engine allow-list through `engines.keep_only`. The change edits one ConfigMap, one tuple in the existing live check, one test module and one document, and builds no code of its own. What SearXNG lacks here: a key-free Stack Exchange engine, and the measure that tells a query rate from a flag on the egress address.

## Dependencies

- #6555 changes `k8s/README.md`, the shared path; this plan edits no line of that file, because the engine list lives in `docs/CLUSTER.md`, so neither change waits for the other.
- The metric devops_cli_web_searches_total also appears in `docs/TELEMETRY.md`, `k8s/devops/monitoring/prometheus-rules-values.yaml`, `src/devops_cli/ai/web_search.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/telemetry/instruments.py`, `openspec/specs/web-search/spec.md`, `openspec/specs/roadmap-alternatives/spec.md`, `openspec/specs/roadmap-service-alerts/spec.md`, `tests/ai/test_web_search.py` and three fixtures under `tests/fixtures/prometheus_rules/`; this change adds no instrument, no label and no alert rule, and the measure itself stays with #4201.
