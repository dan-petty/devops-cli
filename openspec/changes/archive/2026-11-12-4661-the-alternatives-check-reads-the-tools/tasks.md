# Tasks

## 1. Read the tools in use

Kind: behavior. Reads: `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stores/github_store.py`, `tests/support/fakes/roadmap_store.py`. Changes: `src/devops_cli/roadmap/inventory.py`, `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stores/github_store.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `pyproject.toml`, `uv.lock`, the tests below.

- [x] 1.1 Add tests. `dependency_purls` of the GitHub store reads `repos/<repo>/dependency-graph/sbom` and returns the `purl` references, and none for 404; the store contract holds both adapters to the same answer, with an SBOM route in `GitHubFake`. The row `alternatives` needs the clone of its lane and reads its deployed paths. A tool whose package the SBOM holds (a PyPI package, an action, an action with a path, a scoped npm package), a tool that the deployed paths of a clone name, and a GitHub tool whose package deps.dev links give `in-use` with the line "The repository already uses this tool.". A word in another path or in a longer word names no tool. An empty SBOM sends no deps.dev request. A failed deps.dev read skips the item and records `HTTPStatusError`. The census replay gives `in-use` for at least 55 of the 58 tools in use
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_alternatives_project_facts.py tests/roadmap/test_roadmap_alternatives.py tests/roadmap/stores/test_roadmap_store_contract.py tests/roadmap/stores/test_roadmap_github_store_repository.py`
- [x] 1.2 Add `dependency_purls()` to `RoadmapStore`, `GitHubRoadmapStore` and `InMemoryRoadmapStore`. Add `src/devops_cli/roadmap/inventory.py` with `Inventory.uses`, `read_inventory`, `project_of`, `source_project` and `canonical_id`, the deps.dev URL and timeout in `defaults.py`, and `roadmap.alternatives.inventory_paths`. `plan_alternatives` reads the inventory once for a run with an item of no skip class and takes `source`; `validate_reply` gives `in-use` after `rejected` when the inventory holds the tool; `_check_one` turns a failed deps.dev read into a failure of the item. Add `--source` to `devops roadmap alternatives` and `needs_clone` to the row `alternatives`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_alternatives_project_facts.py tests/roadmap/test_roadmap_alternatives.py tests/roadmap/stores/test_roadmap_store_contract.py tests/roadmap/stores/test_roadmap_github_store_repository.py`

## 2. Confirm a rejection only from the rejected options

Kind: behavior. Reads: `src/devops_cli/roadmap/adr.py`. Changes: `src/devops_cli/roadmap/adr.py`, `src/devops_cli/roadmap/alternatives.py`, `tests/roadmap/test_roadmap_adr.py`, `tests/roadmap/test_roadmap_alternatives_project_facts.py`.

- [x] 2.1 Add tests. `rejects` is true for a tool that only rejected or not-chosen options name, and false for a runner-up option, for a chosen option that names the tool too (ADR 0010 and OpenSpec), for a title that names it and for an ADR with no option. A reply with `adr` 10 for OpenSpec keeps `covers`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_adr.py tests/roadmap/test_roadmap_alternatives_project_facts.py`
- [x] 2.2 Add `rejects(adr, *tool_names)` to `src/devops_cli/roadmap/adr.py`, which reads the top-level list items of the options with markdown-it-py, and make `_confirmed_adr` call it
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_adr.py tests/roadmap/test_roadmap_alternatives.py`

## 3. Record the canonical id and the ADR hash, and recheck after an ADR change

Kind: behavior. Changes: `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/stores/store.py`, `tests/roadmap/test_roadmap_alternatives_project_facts.py`, `tests/roadmap/test_roadmap_alternatives.py`, `tests/fixtures/roadmap/alternatives_census.json`.

- [x] 3.1 Add tests. The canonical id of a repository, of a PyPI package with a GitHub source, of a PyPI package with none and of another URL. A PyPI read takes the project of the `Source` URL. A written check records `alternatives.tool_id` and `alternatives.adr_hash`. The 88 tool strings of the census give 81 ids. An item of no skip class with another hash or with no hash is due, and a skip-class item is not. A run reads the ADRs once also when every item is a skip class
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_alternatives_project_facts.py tests/roadmap/test_roadmap_alternatives.py`
- [x] 3.2 Add `TOOL_ID` and `ADR_HASH` to `AlternativesRecordKey`, `project` to `ToolFacts` and `CheckedTool`, the source of a PyPI record (`project_urls`), `adr_hash_of`, and the hash rule of `_is_due`. `plan_alternatives` reads the ADRs before `select_items` and passes their hash
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_alternatives_project_facts.py tests/roadmap/test_roadmap_alternatives.py`

## 4. List the new reads in the dry run

Kind: behavior. Changes: `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_dry_runs.py`.

- [x] 4.1 Add a test. `dry_run_alternatives` lists the ADR reads for each run, the SBOM read under the condition that the run checks an item that is no skip class, and the deps.dev read for each checked item under its condition
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_dry_runs.py`
- [x] 4.2 In `alternatives_requests`, move the ADR reads to the condition of the run, add the SBOM read and the deps.dev read, and add their targets, the method `deps_dev` and the conditions `inventory_read` and `deps_dev_read` to `messages.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_dry_runs.py`

## 5. Documents

Kind: documents. Changes: `docs/roadmap/alternatives.md`, `docs/ROADMAP_WORKFLOW.md`, `CONTEXT.md`, `k8s/README.md`, and the generated documents.

- [x] 5.1 Regenerate the documents for the option `--source` and the setting `roadmap.alternatives.inventory_paths` with `uv run devops docs generate --sync-readme`, and describe the inventory, the rule of a rejecting ADR, the two record keys and the ADR recheck in `docs/roadmap/alternatives.md`, `docs/ROADMAP_WORKFLOW.md`, `CONTEXT.md` and `k8s/README.md`
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- The shared cache of the inventory by commit is the tiered cache item of the plan #4624.
- Pending a person: 7 days after the merge, read the share of `in-use` among the tool verdicts in `devops_cli_roadmap_alternatives_total` (above 25 %, 28 of 130 before).
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
