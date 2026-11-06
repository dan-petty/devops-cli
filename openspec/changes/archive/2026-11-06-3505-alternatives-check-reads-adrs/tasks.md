# Tasks

## 1. Read the ADRs of the repository

Reads: `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/github_store.py`, `src/devops_cli/roadmap/memory_store.py`, `src/devops_cli/roadmap/step_files.py`, `tests/roadmap/test_roadmap_store_contract.py`, `tests/roadmap/test_roadmap_github_store.py`. Changes: `src/devops_cli/roadmap/adr.py`, `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/github_store.py`, `src/devops_cli/roadmap/memory_store.py`, `src/devops_cli/config/constants.py`, `tests/roadmap/test_roadmap_adr.py`, `tests/roadmap/test_roadmap_store_contract.py`, `tests/roadmap/test_roadmap_github_store.py`.

- [x] 1.1 Add tests. `repository_files` of the in-memory store lists the files of one directory at a ref. It leaves out a file of a deeper directory. It raises `GitHubFileNotFoundError` for a directory with no file. `repository_files` of the GitHub store sends the contents request of the directory and returns the paths of the entries of type `file`. It raises as `repository_file` does for a missing directory and for another failure. `tests/roadmap/test_roadmap_adr.py` tests `adr_of` for the number, the title, the status paragraphs and the options. It tests an ADR with no options and a name that is no ADR. It tests `read_adrs` for the newest first, a file that is no ADR, and a missing directory. It also tests an ADR that a later ADR supersedes in whole, which the older or the newer ADR can say. It tests an ADR that is amended or superseded in part, which stays. It tests the entry: the status lines sit between the title and the options
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_adr.py tests/roadmap/test_roadmap_store_contract.py tests/roadmap/test_roadmap_github_store.py` fails on the base
- [x] 1.2 Add `repository_files(directory, *, ref=None) -> list[str]` to `RoadmapStore`, `GitHubRoadmapStore` and `InMemoryRoadmapStore`: the sorted paths of the files directly in the directory, and `GitHubFileNotFoundError` when there is none. The GitHub store sends `repository_file_args` for the directory, validates the JSON array, and shares the not-found and failure handling with `repository_file`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_store_contract.py tests/roadmap/test_roadmap_github_store.py` passes
- [x] 1.3 Add `CONST_ROADMAP_ADR_DIRECTORY` to `src/devops_cli/config/constants.py`. Add `src/devops_cli/roadmap/adr.py` with the frozen dataclass `Adr` (number, title, options, status), `adr_of(path, text)` and `read_adrs(store)`. `adr_of` takes the title from the first level-1 heading. It takes the status from the paragraphs right under it that name an ADR and say supersede or amend. It takes the options from `section_text` of `step_files.py` with the title `considered options`. `read_adrs` gives the ADRs in force, newest first. A missing directory gives an empty tuple
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_adr.py` passes

## 2. Give the model the decisions of the ADRs

Reads: `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/adr.py`, `tests/roadmap/test_roadmap_alternatives.py`, `tests/roadmap/test_roadmap_limit_classes.py`, `tests/roadmap_faults.py`. Changes: `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/adr.py`, `src/devops_cli/config/constants.py`, `tests/roadmap/test_roadmap_alternatives.py`, `tests/roadmap/test_roadmap_adr.py`, `tests/roadmap/test_roadmap_limit_classes.py`, `tests/roadmap_faults.py`.

- [x] 2.1 Add tests for the requirements "The check reads the ADRs of the repository" and "The request holds the decisions of the ADRs". Two ADRs and a superseded one give `decisions` with the newest first, the status lines, and no entry of the superseded ADR. Options over a lowered cap give whole entries, the newest first, and a warning that names each ADR left out. An entry that is over the cap alone is left out, and a smaller older entry stays. A repository with no `docs/adr/` gives no `decisions` key. A run of skip-class items reads no ADR file, which `ListingStore` of `tests/roadmap_faults.py` counts. A failed read of the directory stops the run. Add the new cap to the table of `tests/roadmap/test_roadmap_limit_classes.py` as a share of the planner window. Change the default body of `_item` and the bodies that name `scanner`, so that they name no tool in a marked form
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_adr.py tests/roadmap/test_roadmap_alternatives.py tests/roadmap/test_roadmap_limit_classes.py` fails on the base
- [x] 2.2 Add `CONST_ROADMAP_ALTERNATIVES_MAX_ADR_TOKENS` (8192) to `src/devops_cli/config/constants.py`. Add `fit_to_budget` to `src/devops_cli/roadmap/adr.py`. It keeps whole entries, the newest first, and logs a warning for each ADR it cuts. In `src/devops_cli/roadmap/alternatives.py`, make `plan_alternatives` call `read_adrs` and `fit_to_budget` once, when a selected item is no skip class. Pass the ADRs through `_check_one` to `_request` and `validate_reply`. `_request` adds `decisions`: the entries joined by a blank line, and no key for no ADR
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_adr.py tests/roadmap/test_roadmap_alternatives.py tests/roadmap/test_roadmap_limit_classes.py` passes

## 3. List the ADR reads in the dry run

Reads: `src/devops_cli/roadmap/request_plan.py`, `tests/roadmap/test_roadmap_dry_runs.py`. Changes: `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_dry_runs.py`.

- [x] 3.1 Add a test to `tests/roadmap/test_roadmap_dry_runs.py`. `dry_run_alternatives` lists the `gh` command of the read of `docs/adr` and of the read of one ADR file. Each has its condition and its repeat text
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_dry_runs.py` fails on the base
- [x] 3.2 In `alternatives_requests`, add the read of the directory `CONST_ROADMAP_ADR_DIRECTORY`. Add the read of one ADR file, repeated for each file of it. Both sit under the condition that the run checks an item that is no skip class, and both run once for the run. Add the condition `adr_read` and the repeat `adr_file` to `plan_conditions` and `plan_repeat` in `src/devops_cli/lang/en/messages.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_dry_runs.py` passes

## 4. The model proposes the verdicts, and the job confirms them

Reads: `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/adr.py`, `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/refine_investigation.py`, `src/devops_cli/ai/tasks/roadmap_alternatives.md`, `tests/roadmap/test_roadmap_alternatives.py`, `tests/roadmap/test_roadmap_refine.py`. Changes: `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/adr.py`, `src/devops_cli/roadmap/store.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/ai/tasks/roadmap_alternatives.md`, `tests/roadmap/test_roadmap_alternatives.py`, `tests/roadmap/test_roadmap_adr.py`, `tests/roadmap/test_roadmap_refine.py`.

- [x] 4.1 Add tests for `names` in `tests/roadmap/test_roadmap_adr.py`: the forms of the requirement "A text names a tool by the forms that say so". The six common words `task`, `just`, `requests`, `build`, `rich` and `act` in plain prose name no tool. The same words in a code span, a link or the `owner/name` form do. A name of two words and the display name of the reply name the tool in prose. A longer name such as `pytest-cov` does not
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_adr.py` fails on the base
- [x] 4.2 Add scripted-model tests to `tests/roadmap/test_roadmap_alternatives.py`. A reply that names `temporalio/temporal` with `adr`, and an ADR fixture that rejects Temporal, gives the verdict `rejected`. The comment holds the tool URL and `ADR 0008`, the block names the ADR, and `covers_question` gives no question. The display name `DBOS Transact` confirms an ADR that the repository name `dbos-transact-py` does not. A reply with `in_use` for a tool that the body or the title names in a marked form gives `in-use` and no question. A tool that the item names, with no `in_use`, keeps `covers`. An `in_use` that the item does not back is dropped. A tool that only the block of the check names keeps `covers`, and so does a tool that only the refine section names. A tool with a common word for a name is in use only in a marked form. The job drops four kinds of ADR. They are an unknown one, one that does not name the tool, one that a later ADR supersedes, and one that the cut left out. It writes the check, and refine asks its question. A tool that no ADR rejected and the item does not name keeps `covers` and its question. A repository with no `docs/adr/` gives the verdict of the reply. `rejected` wins over `in-use`. A reply with the verdict `rejected`, `in-use` or `not-applicable` gets one more turn, and the job refuses a second one. Extend the parameters of the test of `tests/roadmap/test_roadmap_refine.py` for a check that adds no question, with `rejected` and `in-use`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_alternatives.py tests/roadmap/test_roadmap_refine.py` fails on the base
- [x] 4.3 Add `REJECTED` (`rejected`) and `IN_USE` (`in-use`) to `Verdict` in `src/devops_cli/roadmap/store.py`. Add `adr`, `in_use` and `tool_name` to `AlternativesReply`, and `adr` to `Check`. Add `names(text, *tool_names)` to `src/devops_cli/roadmap/adr.py`. It reads the text with markdown-it-py and applies the forms. In `src/devops_cli/roadmap/alternatives.py`, make `validate_reply` give `rejected` or `in-use` only when it confirms the proposal. It drops a proposal that it cannot confirm. Compare the title and the body outside both blocks of a job. Move the removal of the two blocks from `body_hash_of` into a helper that both use. Make the output check send back a reply with a verdict that only the job sets, and keep the refusal for a second one. Add the retry message and the line about the basis. Write that line in `_comment_of` and `_block_of`. Add the keys `adr`, `in_use` and `tool_name`, and the rules for them, to the prompt `roadmap_alternatives.md`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_alternatives.py tests/roadmap/test_roadmap_adr.py tests/roadmap/test_roadmap_refine.py` passes

## 5. Document the two verdicts

Reads: `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/ai/tasks/roadmap_refine_proposal.md`, `CONTEXT.md`, `docs/roadmap/alternatives.md`, `k8s/README.md`. Changes: `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/ai/tasks/roadmap_refine_proposal.md`, `CONTEXT.md`, `docs/roadmap/alternatives.md`, `k8s/README.md`, `docs/TELEMETRY.md`.

- [x] 5.1 Name `rejected` and `in-use` in these places. The description of `devops_cli_roadmap_alternatives_total`. The verdict list of the prompt `roadmap_refine_proposal.md`. The entry of `CONTEXT.md` for an alternative. The page `docs/roadmap/alternatives.md`, with the ADRs that the check reads and how the job confirms a proposal. Step 14 of the section "Roadmap service" of `k8s/README.md`. Run `uv run devops docs generate --sync-readme` to write the description to `docs/TELEMETRY.md`
  - Verification: `uv run devops ci docs`

## Criteria

- A reply that names a tool that an ADR rejected gives the verdict `rejected`. The comment holds the tool URL and the ADR number, and refine asks no question.: group 4
- A reply that names a tool that the item body names gives the verdict `in-use`, and refine asks no question.: group 4
- A tool name that only the block of the check holds does not count as in use.: group 4
- A tool that no ADR rejects and that the item does not name keeps `covers` and its question.: group 4
- A repository with no `docs/adr/` gives the same verdict as before this change.: group 2
- The request holds the ADR titles and decisions, cut to a token cap.: group 2

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
