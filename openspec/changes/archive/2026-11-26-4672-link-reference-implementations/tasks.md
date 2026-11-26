# Tasks

## 1. Behavior: the references setting

- [x] 1.1 Write failing tests: the setting is `plan` when it is not set, it holds `off`, `plan` and `on`, a value outside the three is refused, and its variable sets it
  - Verification: `$ uv run devops ci test tests/config/test_alternatives_references_setting.py`
- [x] 1.2 Add `roadmap.alternatives.references` (`RowMode`) with `DEFAULT_ROADMAP_ALTERNATIVES_REFERENCES`, and declare its variable
  - Verification: `$ uv run devops ci test tests/config/test_alternatives_references_setting.py tests/security/test_config_declarations.py`

## 2. Behavior: the reference reads of the roadmap store

- [x] 2.1 Write failing tests: the code search and the repository search send one request each through the session and leave out a private file, the reference facts are one GraphQL read, and a file of another repository is read at its commit
  - Verification: `$ uv run devops ci test tests/roadmap/stores/test_roadmap_github_store_reference_search.py tests/roadmap/stores/test_roadmap_store_reference_reads.py`
- [x] 2.2 Add `CodeSearchHit`, `ReferenceFacts`, `search_code`, `search_repositories`, `reference_facts` and the `repository` keyword of `repository_file` to the store protocol, the GitHub store and the in-memory store
  - Verification: `$ uv run devops ci test tests/roadmap/stores/test_roadmap_github_store_reference_search.py tests/roadmap/stores/test_roadmap_store_reference_reads.py tests/roadmap/stores/test_roadmap_github_store_files.py`

## 3. Behavior: the queries

- [x] 3.1 Write failing tests: the rule queries are the imports, the package names and the code spans of a body, a query names no search qualifier, and the merge takes a rule query and a model query in turn up to the limit
  - Verification: `$ uv run devops ci test tests/roadmap/references/test_reference_queries.py`
- [x] 3.2 Add `references/queries.py` and make `tool_names` of `inventory.py` public
  - Verification: `$ uv run devops ci test tests/roadmap/references/test_reference_queries.py`

## 4. Behavior: the providers, the gates and the rank

- [x] 4.1 Write failing tests: the contract of a provider over the fake and over the GitHub code search, the provider list of a public and of a private repository, and an optional provider that is down at the start
  - Verification: `$ uv run devops ci test tests/roadmap/references/test_reference_provider_contract.py tests/roadmap/references/test_reference_providers.py`
- [x] 4.2 Add `references/providers.py` (the two GitHub providers, `open_providers`, the counter helper), `references/candidates.py` (the gates, the OSI table, the rank) and the instrument `devops_cli_brain_references_total`
  - Verification: `$ uv run devops ci test tests/roadmap/references/test_reference_provider_contract.py tests/roadmap/references/test_reference_providers.py tests/telemetry/test_telemetry_instruments.py`

## 5. Behavior: the step of one item

- [x] 5.1 Write failing tests: the bounds of 3 code searches and 15 fact reads, each gate, the rank, the permalink at the head commit, a path that the head does not hold, the documentation allowlist, the modes, the time bound and the failures that give no error
  - Verification: `$ uv run devops ci test tests/roadmap/references/test_reference_step.py tests/roadmap/references/test_reference_step_github.py`
- [x] 5.2 Add `references/step.py`, and the deps.dev reads `newest_pypi_release`, `direct_dependents` and `Inventory.shared_packages` in `inventory.py`
  - Verification: `$ uv run devops ci test tests/roadmap/references/test_reference_step.py tests/roadmap/references/test_reference_step_github.py tests/roadmap/test_roadmap_alternatives_project_facts.py`

## 6. Behavior: the decision point

- [x] 6.1 Write failing tests: a review band in shadow keeps the rank and counts the decision, a private repository asks nothing, the registry holds the point, and the settings refuse the mode `on`
  - Verification: `$ uv run devops ci test tests/roadmap/references/test_reference_step.py tests/config/test_decision_point_settings.py tests/roadmap/test_roadmap_decision_table.py`
- [x] 6.2 Add `references/relevance.py` with its start cuts file, and register `brain.reference_relevance` in `decision_registry.py` and `decision_table.py`
  - Verification: `$ uv run devops ci test tests/config/test_decision_point_settings.py tests/roadmap/test_roadmap_decision_table.py tests/roadmap/test_roadmap_decision_point.py`

## 7. Behavior: the step in the check

- [x] 7.1 Write failing tests: the step sends the rule queries and the queries of the one reply, a docs item sends the rule queries with no model call, mode `plan` changes no issue, mode `on` writes the block, the comment and `alternatives.refs`, a recheck clears the record, and a down or a held provider leaves the verdict
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_alternatives_references.py`
- [x] 7.2 Add `reference_queries` to the reply and to the prompt `roadmap_alternatives.md`, run the step in `_check_one`, write the links in the block, the comment and the job record, count `linked` at the write, and give `references` in the result line
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_alternatives_references.py tests/roadmap/test_roadmap_alternatives.py tests/roadmap/test_roadmap_alternatives_job_result.py`

## 8. Behavior: the optional MCP provider

- [x] 8.1 Write failing tests: the provider asks the search tool of a server in the process and reads each file link as a code hit, a failed call and a server with no search tool are unavailable, an optional toolset raises at its first refused connection, and a configured server that refuses the connection leaves the run
  - Verification: `$ uv run devops ci test tests/roadmap/references/test_reference_mcp_provider.py tests/roadmap/test_roadmap_mcp_connect_retry.py`
- [x] 8.2 Add the optional mode of `RoadmapMcpToolset`, `references/mcp_provider.py`, `urls_in_order` of `page_fetch.py` and the setting `roadmap.alternatives.references_mcp_url`
  - Verification: `$ uv run devops ci test tests/roadmap/references/test_reference_mcp_provider.py tests/roadmap/test_roadmap_mcp_connect_retry.py tests/roadmap/test_roadmap_page_fetch.py tests/config/test_alternatives_references_setting.py`

## 9. Behavior: the dry run and the limit classes

- [x] 9.1 Write failing tests: the dry run lists the reads of the reference step and none in mode `off`, and each new limit has a class
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_dry_runs.py tests/roadmap/test_roadmap_limit_classes.py`
- [x] 9.2 Add the reads of the step to `alternatives_requests` of `request_plan.py`, with their targets, conditions and repeats in the messages
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_dry_runs.py tests/roadmap/test_roadmap_limit_classes.py`

## 10. Documents

- [x] 10.1 Regenerate the settings references and the telemetry reference with `uv run devops docs generate`, so `docs/CONFIGURATION.md` and `docs/ENV_VARS.md` list `roadmap.alternatives.references` and `docs/TELEMETRY.md` lists the counter
  - Verification: `$ uv run devops ci --check --only docs`
- [x] 10.2 Describe the reference step in `docs/roadmap/alternatives.md`: the modes, the queries, the providers, the gates, the rank, the verification, the documentation allowlist, the bounds, the counter and the decision point
  - Verification: `$ uv run devops ci --check --only docs`

## 11. Behavior: the step fails soft and keeps what it wrote

- [x] 11.1 Write failing tests: a URL that the URL parser refuses stops no step and no check, an error that is no project error gives no link, the thread of the step is a daemon, a failed step in mode `on` and a recheck in mode `plan` or `off` keep the recorded links, a documentation page is read as its source gave it and at most 3 times, and a line ends at a line feed only
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_page_fetch.py tests/roadmap/references/test_reference_step.py tests/roadmap/test_roadmap_alternatives_references.py`
- [x] 11.2 Skip a refused URL candidate in `urls_in_order`, run the step in a daemon thread, add `References.complete` and `recorded_references`, write the links only for a complete step in mode `on`, and pass the sources as their search gave them
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_page_fetch.py tests/roadmap/references/test_reference_step.py tests/roadmap/test_roadmap_alternatives_references.py`

## 12. Behavior: the queries, the gates and the searches

- [x] 12.1 Write failing tests: a query that the guard of the web search refuses reaches no provider, a `.c` file is a code hit, a path with an empty or a dot segment is dropped, and one search is one request for a short page that links a next page
  - Verification: `$ uv run devops ci test tests/roadmap/references/test_reference_queries.py tests/roadmap/references/test_reference_step.py tests/roadmap/stores/test_roadmap_github_store_reference_search.py`
- [x] 12.2 Pass each query through `_guard` of `ai/web_search.py`, test the suffix of a path against `_PROSE_SUFFIXES`, drop a path with an empty or a dot segment, and read one page of a search with `rest`
  - Verification: `$ uv run devops ci test tests/roadmap/references/test_reference_queries.py tests/roadmap/references/test_reference_step.py tests/roadmap/stores/test_roadmap_github_store_reference_search.py`

## 13. Behavior: the errors of the optional MCP provider

- [x] 13.1 Write failing tests: a tool listing that answers with an error or does not answer in the bound is unavailable, a failed call ends the connection, a failed close stops no run, and a query that the optional provider fails goes to the GitHub code search
  - Verification: `$ uv run devops ci test tests/roadmap/references/test_reference_mcp_provider.py tests/roadmap/references/test_reference_providers.py`
- [x] 13.2 Turn the named errors of the MCP libraries into `RoadmapMcpUnavailableError` in `_unavailable`, bound the connection and the tool listing, guard the close in `open_providers`, and send a failed query to the first code provider
  - Verification: `$ uv run devops ci test tests/roadmap/references/test_reference_mcp_provider.py tests/roadmap/references/test_reference_providers.py`

## 14. Behavior: the dry run of the configured requests

- [x] 14.1 Write a failing test: the dry run lists the MCP tool call and the decision model call when they are configured, and neither by default
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_dry_runs.py`
- [x] 14.2 Add the two rows to `_reference_requests` of `request_plan.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_dry_runs.py`

## 15. Manifest and documents

- [x] 15.1 Add `references: plan` with its comment to the `alternatives` block of `k8s/devops/configmap.example.yaml`
  - Verification: `$ uv run devops ci --check --only k8s`
- [x] 15.2 Describe the guard, the kept links, the page reads, the two link bounds and the errors of the optional provider in `docs/roadmap/alternatives.md`, and regenerate the telemetry reference
  - Verification: `$ uv run devops ci --check --only docs`

## Workflow follow-up

- The switch of `roadmap.alternatives.references` to `on` is #6588.
- The move of the step into the research unit is #5513.
- Pending a person: after the merge and the release, run the check as the App in mode `plan` on 5 items of the stage window, and give the result lines in a comment on #4672. `devops_cli_brain_references_total` then holds a point for each item.
- Pending a person: set `roadmap.alternatives.references_mcp_url` in the cluster configuration to use the grep.app server. No request went to that server in this change.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
