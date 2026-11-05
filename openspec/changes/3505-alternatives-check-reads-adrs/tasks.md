# Tasks

## 1. Read the ADRs of the repository

Reads: `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/github_store.py`, `src/devops_cli/roadmap/memory_store.py`, `src/devops_cli/roadmap/step_files.py`, `tests/roadmap/test_roadmap_store_contract.py`, `tests/roadmap/test_roadmap_github_store.py`. Changes: `src/devops_cli/roadmap/adr.py`, `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/github_store.py`, `src/devops_cli/roadmap/memory_store.py`, `src/devops_cli/config/constants.py`, `tests/roadmap/test_roadmap_adr.py`, `tests/roadmap/test_roadmap_store_contract.py`, `tests/roadmap/test_roadmap_github_store.py`.

- [x] 1.1 Add tests: `repository_files` of the in-memory store lists the files of one directory at a ref, leaves out a file of a deeper directory, and raises `GitHubFileNotFoundError` for a directory with no file; `repository_files` of the GitHub store sends the contents request of the directory, returns the paths of the entries of type `file`, and raises as `repository_file` does for a missing directory and for another failure; `tests/roadmap/test_roadmap_adr.py` holds tests for `adr_of` (number, title, options; no options; a name that is no ADR), for `read_adrs` (newest first, a file that is no ADR left out, a missing directory gives no ADR) and for `names` (the four scenarios of the requirement "A text names a tool by its name as a whole word")
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_adr.py tests/roadmap/test_roadmap_store_contract.py tests/roadmap/test_roadmap_github_store.py` fails on the base
- [x] 1.2 Add `repository_files(directory, *, ref=None) -> list[str]` to `RoadmapStore`, `GitHubRoadmapStore` and `InMemoryRoadmapStore`: the sorted paths of the files directly in the directory, and `GitHubFileNotFoundError` when there is none. The GitHub store sends `repository_file_args` for the directory, validates the JSON array, and shares the not-found and failure handling with `repository_file`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_store_contract.py tests/roadmap/test_roadmap_github_store.py` passes
- [x] 1.3 Add `CONST_ROADMAP_ADR_DIRECTORY` to `src/devops_cli/config/constants.py`, and `src/devops_cli/roadmap/adr.py` with the frozen dataclass `Adr` (number, title, options), `adr_of(path, text)`, `read_adrs(store)` (newest first, a missing directory gives an empty tuple) and `names(text, name)`. `adr_of` takes the title from the first level-1 heading and the options from `section_text` of `step_files.py` with the title `considered options`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_adr.py` passes

## 2. Give the model the decisions of the ADRs

Reads: `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/adr.py`, `tests/roadmap/test_roadmap_alternatives.py`. Changes: `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/config/constants.py`, `tests/roadmap/test_roadmap_alternatives.py`.

- [x] 2.1 Add tests to `tests/roadmap/test_roadmap_alternatives.py` for the requirements "The check reads the ADRs of the repository" and "The request holds the decisions of the ADRs": two ADRs give `decisions` with the newest first; options longer than a lowered cap give a cut text that starts with the newest ADR; a repository with no `docs/adr/` gives no `decisions` key; a run of skip-class items reads no ADR file; a failed read of the directory stops the run and writes no check. Change the default body of `_item` and the bodies that name `scanner` so that they name no tool, since a body that names the tool now gives the verdict `in-use`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_alternatives.py` fails on the base
- [x] 2.2 Add `CONST_ROADMAP_ALTERNATIVES_MAX_ADR_TOKENS` (8192) to `src/devops_cli/config/constants.py`. In `src/devops_cli/roadmap/alternatives.py`, make `plan_alternatives` call `read_adrs` once when a selected item is no skip class, pass the ADRs through `_check_one` to `_request`, and add `decisions` to the request: the entries `ADR <number as four digits>: <title>` and the options, joined by a blank line, cut with `truncate_to_token_limit`, and no key for no ADR
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_alternatives.py` passes

## 3. List the ADR reads in the dry run

Reads: `src/devops_cli/roadmap/request_plan.py`, `tests/roadmap/test_roadmap_dry_runs.py`. Changes: `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_dry_runs.py`.

- [x] 3.1 Add to `tests/roadmap/test_roadmap_dry_runs.py` a test that `dry_run_alternatives` lists the `gh` command of the read of `docs/adr` and of the read of one ADR file, each with its condition and repeat text
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_dry_runs.py` fails on the base
- [x] 3.2 In `alternatives_requests`, add the read of the directory `CONST_ROADMAP_ADR_DIRECTORY` and, repeated for each file of it, the read of one ADR file, both under the condition that the run checks an item that is no skip class and once for the run. Add the condition `adr_read` and the repeat `adr_file` to `plan_conditions` and `plan_repeat` in `src/devops_cli/lang/en/messages.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_dry_runs.py` passes

## 4. Give the verdicts rejected and in-use

Reads: `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/adr.py`, `src/devops_cli/roadmap/store.py`, `src/devops_cli/ai/tasks/roadmap_alternatives.md`, `tests/roadmap/test_roadmap_alternatives.py`, `tests/roadmap/test_roadmap_refine.py`. Changes: `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/store.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/ai/tasks/roadmap_alternatives.md`, `tests/roadmap/test_roadmap_alternatives.py`, `tests/roadmap/test_roadmap_refine.py`.

- [x] 4.1 Add scripted-model tests to `tests/roadmap/test_roadmap_alternatives.py`: a reply that names `temporalio/temporal` with an ADR fixture that rejects Temporal gives the verdict `rejected`, a comment with the tool URL and `ADR 0008`, a block that names the ADR, and no question from `covers_question`; a reply for a tool that the item body names gives `in-use` and no question; a tool that only the block of the check names, and one that only the refine section names, keep `covers`; a tool that no ADR rejected and the item does not name keeps `covers` and its question; a repository with no `docs/adr/` gives the verdict of the reply; a reply with an unknown ADR number, an ADR that does not name the tool, or the verdict `rejected` or `in-use` is refused; `rejected` wins over `in-use`. Extend the parameters of the test of `tests/roadmap/test_roadmap_refine.py` for a check that adds no question with `rejected` and `in-use`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_alternatives.py tests/roadmap/test_roadmap_refine.py` fails on the base
- [x] 4.2 Add `REJECTED` (`rejected`) and `IN_USE` (`in-use`) to `Verdict` in `src/devops_cli/roadmap/store.py` and update its docstring. Add `adr: int | None` to `AlternativesReply` and `adr: int | None` to `Check`. In `src/devops_cli/roadmap/alternatives.py`, make `_refusal` refuse the verdicts that only the job sets, an ADR that the repository does not hold and an ADR that does not name the tool, and make `validate_reply` take the ADRs and set `rejected` or `in-use` as the design says. Compare with the title and the body outside both blocks: move the removal of the two blocks from `body_hash_of` into a helper that both use. Add the messages for the three refusals and for the line about the basis, and write that line in `_comment_of` and `_block_of`. Add the key `adr` and the two verdicts to the prompt `roadmap_alternatives.md`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_alternatives.py tests/roadmap/test_roadmap_refine.py` passes

## 5. Document the two verdicts

Reads: `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/ai/tasks/roadmap_refine_proposal.md`, `CONTEXT.md`, `docs/roadmap/alternatives.md`, `k8s/README.md`. Changes: `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/ai/tasks/roadmap_refine_proposal.md`, `CONTEXT.md`, `docs/roadmap/alternatives.md`, `k8s/README.md`, `docs/TELEMETRY.md`.

- [ ] 5.1 Name `rejected` and `in-use` in the description of `devops_cli_roadmap_alternatives_total`, in the verdict list of the prompt `roadmap_refine_proposal.md`, in the entry of `CONTEXT.md` for an alternative, in `docs/roadmap/alternatives.md` (what a check does, and the ADRs it reads) and in step 14 of the section "Roadmap service" of `k8s/README.md`. Run `uv run devops docs generate --sync-readme` to write the description to `docs/TELEMETRY.md`
  - Verification: `uv run devops ci docs` passes

## Criteria

- A reply that names a tool that an ADR rejected gives the verdict `rejected`, the comment holds the tool URL and the ADR number, and refine asks no question.: group 4
- A reply that names a tool that the item body names gives the verdict `in-use`, and refine asks no question.: group 4
- A tool name that only the block of the check holds does not count as in use.: group 4
- A tool that no ADR rejects and that the item does not name keeps `covers` and its question.: group 4
- A repository with no `docs/adr/` gives the same verdict as before this change.: group 2
- The request holds the ADR titles and decisions, cut to a token cap.: group 2

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
