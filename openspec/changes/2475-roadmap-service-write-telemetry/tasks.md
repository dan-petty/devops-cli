# Tasks

## 1. Name the method, repository and row of each GitHub request

- [x] Add failing tests: a job row's comment counts its method, repository and row; a request outside a scope counts `other`; a gh command other than `gh api` counts POST for a write and GET for a read; a session request counts the scope of the thread that sent it; a worker's round and each row run in their scopes
  - Verification: `uv run devops ci test tests/test_github_api_metrics.py tests/test_service_limits.py`
- [x] Add `github/request_scope.py`, the `method` of `acquire` from `run_gh` and the session, and the scopes of `RepoWorker._execute_batch` and `_execute_due_rows`; describe the labels in `GITHUB_REQUESTS_TOTAL`
  - Verification: `uv run devops ci test tests/test_github_api_metrics.py tests/test_service_limits.py`

## 2. Show the budget, its holds and the suspended jobs

- [x] Add failing tests: the budget's gauges and hold counter follow the window; a job's suspension gauge follows its failures and its success; a restart shows the kept budget and suspension
  - Verification: `uv run devops ci test tests/test_service_limits.py`
- [x] Publish the gauges and the counter from `RequestBudget` and `FailureLedger`
  - Verification: `uv run devops ci test tests/test_service_limits.py tests/test_server_service.py`

## 3. Count the App bot's own deliveries as self

- [x] Add a failing test: the bot's write counts as outcome `self`, apart from a repeated delivery
  - Verification: `uv run devops ci test tests/test_server_service.py`
- [x] Map the refusal status `ignored_own_write` to the outcome `self`
  - Verification: `uv run devops ci test tests/test_server_service.py`

## 4. Count each Firecrawl search, and warn on a failed one

- [x] Add failing tests: a search counts `ok`; a 401, 402, 429 or 500 counts its status and logs one warning with no key or query; no answer or no web results counts `error`
  - Verification: `uv run devops ci test tests/test_common_tools.py`
- [x] Declare `FIRECRAWL_SEARCHES_TOTAL`, and count and log in `firecrawl_search`
  - Verification: `uv run devops ci test tests/test_common_tools.py tests/test_roadmap_refine_investigation.py`

## 5. Cap refine's comments on one item

- [x] Add failing tests: two refine comments within 24 hours leave the item waiting on a person with no model call, no comment, one warning and one count; the same comments 25 hours old do not; items at the cap take no place under the limit; a round with no newer comment writes, logs and counts nothing, and a newer reply counts once; `--item` refines an item at the cap; a round's plan lists the record write of a stop
  - Verification: `uv run devops ci test tests/test_roadmap_refine.py tests/test_roadmap_dry_runs.py`
- [x] Declare `ROADMAP_REFINE_COMMENTS_CAPPED_TOTAL` and `RefineRecordKey.CAPPED_AFTER`, apply the cap in `_Selection.consider`, and record, log and count each new stop in `apply_refine`
  - Verification: `uv run devops ci test tests/test_roadmap_refine.py tests/test_roadmap_dry_runs.py`
- [x] Say in the help of `devops roadmap refine` and in `k8s/README.md` how the cap holds an item and how a person refines it, and regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 6. Alert on the writes, the own deliveries and the Firecrawl refusals

- [x] Add failing tests: the group `roadmap-service-activity` pins its three rules, selects only the Service, points each alert to the README, and passes its promtool unit tests
  - Verification: `uv run devops ci test tests/test_k8s_monitoring_alerting.py`
- [x] Add the group to `k8s/monitoring/prometheus-values.yaml` and its unit tests to `tests/fixtures/prometheus_rules/roadmap_service_activity_tests.yaml`
  - Verification: `uv run devops ci test tests/test_k8s_monitoring_alerting.py`
- [x] Say in `k8s/README.md` what to do for each alert and where the new series are, and regenerate the documentation
  - Verification: `uv run devops ci test tests/test_k8s_monitoring_alerting.py tests/test_docs.py` and `uv run devops docs generate --sync-readme`

## 7. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 2475-roadmap-service-write-telemetry`
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
