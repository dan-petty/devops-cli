# Proposal

## Why

Issue #3505: the alternatives check can give the verdict `covers` for a tool that an ADR of the project rejected. It can also give `covers` for a tool that the item already names. Refine then asks a person to adopt the tool or to keep the item. The repository already answers that question. Five `covers` verdicts of 2026-11-01 to 2026-11-04 got the question. The question of #3062 (`temporalio/temporal`, rejected by ADR 0008) is one of them. The cause is in two places. `_request` in `src/devops_cli/roadmap/alternatives.py` gives the model the item and the replies but no ADR. No code compares the tool of the reply with the text of the item.

## What Changes

- A new store method `repository_files(directory)` lists the files of one directory through the GitHub contents API. It is in `RoadmapStore`, `GitHubRoadmapStore` and `InMemoryRoadmapStore`. A missing directory raises `GitHubFileNotFoundError`, as `repository_file` does for a missing file.
- A new module `src/devops_cli/roadmap/adr.py` reads the ADRs of `docs/adr/`. For each ADR it keeps the number, the title, the status paragraphs under the title and the `Considered Options` section. It reads them with markdown-it-py, through `section_text` of `step_files.py`.
- The status paragraphs reach the model, so it can see that an ADR is amended. The module also leaves out an ADR that a later ADR supersedes in whole, so the model never reads a decision that no longer holds.
- `fit_to_budget` in the same module cuts the entries to `CONST_ROADMAP_ALTERNATIVES_MAX_ADR_TOKENS`. It takes whole entries only and logs a warning that names each ADR that it leaves out. The job confirms only the ADRs that the model saw.
- `names(text, *tool_names)` tests whether a text names a tool. It reads the text with markdown-it-py. A name of two words or more counts anywhere. A name of one word, such as `just`, counts only in a code span, a link or strong emphasis. The full `owner/name` counts anywhere.
- `plan_alternatives` reads the ADRs once for a run, only when the run checks an item that is no skip class. `_request` adds the key `decisions` with the entries. A repository with no `docs/adr/` gives no key and no other change.
- `AlternativesReply` gets three optional keys. `adr` is the number of the ADR that rejected the tool. `in_use` says that the item already names the tool. `tool_name` is the name that the ADR or the item writes for the tool, such as `DBOS Transact`.
- `Verdict` gets two values, `rejected` and `in-use`. The model proposes each one with its key, and the job gives it only when the text confirms it. If the job cannot confirm a proposal, it drops the proposal, keeps the verdict of the reply and writes the check.
- The model cannot give `rejected`, `in-use` or `not-applicable` as its verdict. The output check that already retries a reply with no search also retries such a verdict once. The job refuses a second one.
- The comment and the block of a `rejected` check name the ADR, and the comment keeps the tool URL.
- Refine needs no code change: `covers_question` asks only for a `covers` verdict, so a `rejected` or `in-use` check adds no question. A test pins that.
- The dry run of `devops roadmap alternatives` lists the read of `docs/adr` and of each ADR file.
- The prompts, `CONTEXT.md`, `docs/roadmap/alternatives.md`, `k8s/README.md` and the description of `devops_cli_roadmap_alternatives_total` name the two new verdicts.
- The change has a spec delta, because a verdict, a request key and a dry-run line are observable (`openspec/config.yaml`).
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-alternatives`: the ADR read, the `decisions` key, the forms of a tool name and the confirmed verdicts.
- `roadmap-refine`: a `rejected` or `in-use` check adds no question.

## Impact

- Code: `src/devops_cli/roadmap/adr.py` (new), `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/github_store.py`, `src/devops_cli/roadmap/memory_store.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/telemetry/instruments.py`
- Prompts: `src/devops_cli/ai/tasks/roadmap_alternatives.md`, `src/devops_cli/ai/tasks/roadmap_refine_proposal.md`
- Tests: `tests/roadmap/test_roadmap_adr.py` (new), `tests/roadmap/test_roadmap_alternatives.py`, `tests/roadmap/test_roadmap_store_contract.py`, `tests/roadmap/test_roadmap_github_store.py`, `tests/roadmap/test_roadmap_dry_runs.py`, `tests/roadmap/test_roadmap_refine.py`, `tests/roadmap_faults.py`
- Documents: `CONTEXT.md`, `docs/roadmap/alternatives.md`, `k8s/README.md`, `docs/TELEMETRY.md` (generated)
- Left as they are, on purpose: `src/devops_cli/commands/roadmap_eval.py`, which has no alternatives set, so the tests use a scripted model. `docs/ROADMAP_WORKFLOW.md` does not list the verdicts. The retry rule `_in_retry_delay` stays, because a failed check is not part of this item.

## Dependencies

- #2950 (open plan, change `2950-alternatives-coverage-gauge-searches-per-check`) adds requirements to `roadmap-alternatives` and edits `select_items`, `Selection`, `AlternativesPlan` and `apply_alternatives` in `alternatives.py`. This change edits `_request`, `validate_reply`, `_refusal`, `_check_one`, `plan_alternatives`, `Check` and the comment and block writers. Neither change modifies a requirement of the other, so the order of the merges does not matter. The change that merges second merges `main` and keeps both edits of `plan_alternatives`.
- #2951 makes an alternatives verdict a condition of Ready, so more verdicts reach a person. The issue asks for this change to land before #2951. Nothing in this change waits for #2951.

## Feasibility

- The premise holds for the ADR case. `docs/adr/0008-argo-workflows-run-the-roadmap-jobs-after-a-measured-go.md` line 20 reads "Temporal and Hatchet: rejected. Each needs a new Postgres and 3-6 pods." The job record of #3062 holds the verdict `covers` and the tool `https://github.com/temporalio/temporal`. It was read with `uv run devops gh api repos/dan-petty/devops-cli/issues/3062` on 2026-11-05. The line sits under `## Considered Options`, so the check reads that section.
- The directory read works. `uv run devops gh api repos/dan-petty/devops-cli/contents/docs/adr` returned 17 entries, each with `name`, `path` and `type` `file`. The same call with the header `Accept: application/vnd.github.raw+json` returned the same JSON array. `repository_file_args` sends that header for a file. So the argument builder of a file read serves a directory read, and the store needs one new method and no new endpoint.
- The size fits a request. A scratch script built the entries of the ADRs with `Adr.entry` and counted them with `count_tokens`. The 14 ADRs in force hold 4,779 tokens, status lines included. The cap `CONST_ROADMAP_ALTERNATIVES_MAX_ADR_TOKENS` is 8,192, half of `CONST_ROADMAP_ALTERNATIVES_MAX_BODY_TOKENS`. The 17 ADRs hold about 64,000 tokens in all, more than the window of one run. So the check reads the options only.
- Real ADRs show that a bare name match is not enough, so the job does not decide on one. Two independent reviews ran the first name rule over this repository. ADR 0011 is superseded by ADR 0012, which adopted release-please. Yet its option line says "A. Trunk with release-please ... rejected for now". The rule named release-please there, so the check would have given `rejected` for a tool that the project uses. The rule also named `just`, `task`, `requests`, `build`, `rich` and `act` in ordinary sentences. It missed "DBOS Transact" for the repository `dbos-inc/dbos-transact-py`. So the model proposes both verdicts, and the job only confirms them.
- The status of each ADR is in its first paragraphs. A scratch script read the first paragraphs of the 17 ADRs. ADR 0002, 0011 and 0012 say "ADR NNNN supersedes this ADR". ADR 0013 and ADR 0015 say that they supersede ADR 0012 and ADR 0002. ADR 0003 and ADR 0017 say that one clause is superseded, so both stay. The 14 ADRs in force are 1, 3 to 10 and 13 to 17. No ADR has a structured status field. So the job reads the sentence, and it also shows the status lines to the model.
- The `in-use` case was run on the live text. A scratch script took the body of #3025, #1357, #1387 and #2003 as `Item.body` holds it. It split off the job record and removed the block of the check and the refine section. `names` found `grafana` in strong emphasis in #1357. It found `notifications-engine`, a name of two words, in #1387 and #2003. It found `pytest` in no part of #3025. So the job can confirm `in-use` for 3 of the 4 item cases when the model flags it. #3025 keeps its `covers` verdict. Its item names no tool, and no rule over the text can see that pytest runs the test. The issue claims all five verdicts, but its acceptance criteria name only the cases that a test can pin.
- A deviation from the issue text. The issue says to read the text outside the block of the check, "as `_request` does". The refine section of #3025 holds the open question "The alternatives check found that `https://github.com/pytest-dev/pytest` covers this item". So that section names the tool because of the earlier check. A rule that reads it would turn each later `covers` check of the item into `in-use`. That would close a question that no person answered. So the comparison reads the text outside both blocks, and a test pins it. `_request` keeps its text.
- `covers_question` in `src/devops_cli/roadmap/refine.py` (line 518) returns a question only for the verdict `COVERS`. `_covering_tool` and `_needs_second_look` read only that verdict. A `rejected` or `in-use` check therefore needs no change in refine.
- `_retry_once` in `src/devops_cli/roadmap/refine_investigation.py` gives the model one more turn for the first reply that the output check does not accept. The output check of this job now returns a message for a verdict that only the job sets. So a natural reply gets the same retry as a reply with no search.
- Not verified: how the live model fills `adr`, `in_use` and `tool_name` for a repository with many ADRs. The tests use a scripted model, as the issue says, since `devops roadmap eval` has no alternatives set. A wrong value ends as a dropped proposal, and the check keeps the verdict of the reply.

## Existing Tool Considered

The ADRs are data that the project already keeps in `docs/adr/`. markdown-it-py, which `refine.py` and `step_files.py` already use, reads their sections and their status paragraphs. It also finds the code spans, links and strong emphasis of a text. `section_text` in `src/devops_cli/roadmap/step_files.py` returns the `Considered Options` section, so the change adds no parser. The GitHub contents API, through the `gh` runner of the store, lists the directory. The stdlib `re` module tests a whole-word name inside the spans that markdown-it-py finds. The change adds no library.

The ADRs have no structured status field, such as the YAML front matter of MADR. Adding one to each ADR is a larger change than this item. So the job reads the status sentence and shows it to the model. No open tool decides whether an ADR rejected a tool. So the model correlates the ADRs with the reply, and the job confirms the claim against the text. A word list or a fuzzy-match library could tell a common word from a coined name. Both would add a dependency for a gate that a marked form already serves, so the change adds neither.

Cost of the first build: about 150,000 tokens and 4 hours elapsed. Cost of the rework after two reviews: about 250,000 tokens and 4 hours more. Cost to keep: about 5,000 tokens each time the ADR format or the verdict list changes. Cost to fix: one failing test that names the case, about 10,000 tokens. The change deletes no internal code.
