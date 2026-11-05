# Proposal

## Why

Issue #3505: the alternatives check can give the verdict `covers` for a tool that an ADR of the project rejected, or for a tool that the item already names. Refine then asks a person to adopt the tool or to keep the item, and the repository already answers that question. Five `covers` verdicts of 2026-11-01 to 2026-11-04 got the question, and the question of #3062 (`temporalio/temporal`, rejected by ADR 0008) is one of them. The cause is in two places. `_request` in `src/devops_cli/roadmap/alternatives.py` gives the model the item and the replies but no ADR. No code compares the tool of the reply with the text of the item.

## What Changes

- A new store method `repository_files(directory)` lists the files of one directory of the repository through the GitHub contents API, in `RoadmapStore`, `GitHubRoadmapStore` and `InMemoryRoadmapStore`. A missing directory raises `GitHubFileNotFoundError`, as `repository_file` does for a missing file.
- A new module `src/devops_cli/roadmap/adr.py` reads the ADRs of `docs/adr/`. For each ADR it keeps the number, the title and the text of the `Considered Options` section, with markdown-it-py through `section_text` of `step_files.py`. It also holds `names`, the test whether a text names a tool as a whole word.
- `plan_alternatives` reads the ADRs once for a run, only when the run checks an item that is no skip class. `_request` adds the key `decisions`: the ADRs, the newest first, cut to `CONST_ROADMAP_ALTERNATIVES_MAX_ADR_TOKENS`. A repository with no `docs/adr/` gives no key and no other change.
- `AlternativesReply` gets the optional key `adr`: the number of the ADR that rejected the tool. The job accepts it only when the repository holds that ADR and the ADR names the tool; else it refuses the reply, as it refuses a URL that no tool returned.
- `Verdict` gets two values that only the job sets: `rejected` (the reply names an ADR that the job confirmed) and `in-use` (the title or the body of the item names the tool). The job refuses both from the model.
- `validate_reply` sets `in-use` by code, with no model: it compares the name of the tool with the text of the item outside the block of the check and outside the refine section. The comment and the block of a `rejected` check name the ADR, and the comment keeps the tool URL.
- Refine needs no code change: `covers_question` asks only for a `covers` verdict, so a `rejected` or `in-use` check adds no question. A test pins that.
- The dry run of `devops roadmap alternatives` lists the read of `docs/adr` and of each ADR file.
- The prompts, `CONTEXT.md`, `docs/roadmap/alternatives.md`, `k8s/README.md` and the description of `devops_cli_roadmap_alternatives_total` name the two new verdicts.
- The change has a spec delta: a verdict, a request key and a dry-run line are observable (`openspec/config.yaml`).
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-alternatives`: The check reads the ADRs of the repository, The request holds the decisions of the ADRs, A text names a tool by its name as a whole word, An ADR that rejected the tool gives the verdict rejected, The job refuses a rejection that it cannot confirm, An item that names the tool gives the verdict in-use
- `roadmap-refine`: A rejected or in-use check adds no question

## Impact

- Code: `src/devops_cli/roadmap/adr.py` (new), `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/github_store.py`, `src/devops_cli/roadmap/memory_store.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/telemetry/instruments.py`
- Prompts: `src/devops_cli/ai/tasks/roadmap_alternatives.md`, `src/devops_cli/ai/tasks/roadmap_refine_proposal.md`
- Tests: `tests/roadmap/test_roadmap_adr.py` (new), `tests/roadmap/test_roadmap_alternatives.py`, `tests/roadmap/test_roadmap_store_contract.py`, `tests/roadmap/test_roadmap_github_store.py`, `tests/roadmap/test_roadmap_dry_runs.py`, `tests/roadmap/test_roadmap_refine.py`
- Documents: `CONTEXT.md`, `docs/roadmap/alternatives.md`, `k8s/README.md`, `docs/TELEMETRY.md` (generated)
- Left as they are, on purpose: `src/devops_cli/commands/roadmap_eval.py` (it has no alternatives set, so the tests use a scripted model), `docs/ROADMAP_WORKFLOW.md` (it does not list the verdicts), and the retry rule `_in_retry_delay` (a failed check is not part of this item).

## Dependencies

- #2950 (open plan, change `2950-alternatives-coverage-gauge-searches-per-check`) adds requirements to `roadmap-alternatives` and edits `select_items`, `Selection`, `AlternativesPlan` and `apply_alternatives` in `alternatives.py`. This change edits `_request`, `validate_reply`, `_refusal`, `_check_one`, `plan_alternatives`, `Check` and the comment and block writers. Neither change modifies a requirement of the other, so the order of the merges does not matter. The change that merges second merges `main` and keeps both edits of `plan_alternatives`.
- #2951 makes an alternatives verdict a condition of Ready, so more verdicts reach a person. The issue asks for this change to land before #2951. Nothing in this change waits for #2951.

## Feasibility

- The premise holds for the ADR case. `docs/adr/0008-argo-workflows-run-the-roadmap-jobs-after-a-measured-go.md` line 20 reads "Temporal and Hatchet: rejected. Each needs a new Postgres and 3-6 pods." The job record of #3062, read with `uv run devops gh api repos/dan-petty/devops-cli/issues/3062` on 2026-11-05, holds the verdict `covers` and the tool `https://github.com/temporalio/temporal`. The bullet sits under `## Considered Options`, so the check reads that section.
- The directory read works. `uv run devops gh api repos/dan-petty/devops-cli/contents/docs/adr` returned 17 entries, each with `name`, `path` and `type` `file`. The same call with the header `Accept: application/vnd.github.raw+json`, which `repository_file_args` sends for a file, returned the same JSON array. So the argument builder of a file read serves a directory read, and the store needs one new method and no new endpoint.
- The size fits a request. The `Considered Options` sections of the 17 ADRs hold about 6,000 tokens (characters divided by 4, measured with a scratch script over `docs/adr/`). The cap `CONST_ROADMAP_ALTERNATIVES_MAX_ADR_TOKENS` is 8,192, half of `CONST_ROADMAP_ALTERNATIVES_MAX_BODY_TOKENS`. The 17 ADRs hold about 64,000 tokens in all (256,749 characters divided by 4), more than the window of one run, so the check reads the options only.
- The name rule was run on the live text. A scratch script took the title and the body of #3025, #1357, #1387 and #2003 as `Item.body` holds them (no record block), removed the block of the check and the refine section, and tested the last segment of the tool name as a whole word. It found `grafana` in #1357 and `notifications-engine` in #1387 and #2003, and found `pytest` in no part of #3025. So the code decides 3 of the 4 item cases, and #3025 keeps its `covers` verdict: its item names no tool, and no rule over the text can see that pytest runs the test. The issue claims all 5 verdicts as evidence, but its acceptance criteria name only the two cases that the code can decide, and this change does not widen them.
- A deviation from the issue text. The issue says to read the text outside the block of the check, "as `_request` does". The refine section of #3025 holds the open question "The alternatives check found that `https://github.com/pytest-dev/pytest` covers this item", so the refine section names the tool because of the earlier check. A rule that reads it would turn every later `covers` check of that item into `in-use` and close the question that a person has not answered. So the comparison reads the text outside both blocks, and a test pins it. `_request` keeps its text.
- `src/devops_cli/roadmap/refine.py` `covers_question` (line 524) returns a question only for the verdict `COVERS`, and `_covering_tool` and `_needs_second_look` read only that verdict. A `rejected` or `in-use` check therefore needs no change in refine.
- The line numbers of the issue are close: `_request` is at line 535, `validate_reply` at line 758 (the issue says 757) and `_in_retry_delay` at line 479.
- Not verified: how the live model fills `adr` for a repository with many ADRs. The tests use a scripted model, as the issue says, since `devops roadmap eval` has no alternatives set. The job confirms every `adr` against the text of the ADR, so a wrong value ends as a refused reply and a retry, not as a wrong verdict.

## Existing Tool Considered

The ADRs are data that the project already keeps in `docs/adr/`. markdown-it-py, which `refine.py` and `step_files.py` already use, reads their sections: `section_text` in `src/devops_cli/roadmap/step_files.py` returns the `Considered Options` section, so the change adds no parser. The GitHub contents API, through the `gh` runner of the store, lists the directory. The stdlib `re` module tests a whole-word name. The change adds no library. No open tool decides whether an ADR rejected a tool, so the model correlates the ADRs with the reply, and the job confirms the claim against the ADR text. Cost of building the reader, the name rule and the two verdicts: about 150,000 tokens and 4 hours elapsed with the CI waits (five groups, four of them with a failing test first). Cost to keep: about 5,000 tokens each time the ADR format or the verdict list changes. Cost to fix: one failing test that names the case, about 10,000 tokens. The change deletes no internal code.
