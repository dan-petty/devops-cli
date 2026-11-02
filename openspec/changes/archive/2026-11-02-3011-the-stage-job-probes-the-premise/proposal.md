# Proposal

## Why

The stage job cannot run a command, so `## Feasibility` of most plans holds only checks that the implementation will run later. Four plans of the 2026-11-01 evaluation rested on a premise that was already false (#2984, #2981, #2985, #2857). AGENTS.md rule 2 asks for the evidence first and says to return an item whose premise is false. The job must probe the premise at the staging commit and return the item (#3011).

## What Changes

- Add `src/devops_cli/roadmap/stage_probe.py`. `probe_premise(source, sha, body)` takes the paths and identifiers that the issue cites, runs at most 10 read-only git commands at the staging commit, and returns the probe text with the items it skipped. For a path it asks whether the path exists and, for a missing one, which commit deleted or renamed it. For an identifier it asks for the definition and, for a missing one, which commit last added or removed the text.
- Expose the extraction of `collect_context` instead of writing a second one. `src/devops_cli/roadmap/refine.py` gets the public `cited_paths(body)`, `cited_identifiers(body)` and `git_result`, and its collectors use them.
- Put the probe text in the model input of `_Planner._request` in `src/devops_cli/roadmap/stage.py`, under the key `probes`.
- Add the field `premise_failed` to `StageProposal` in `src/devops_cli/roadmap/stage_change.py`. A reply that sets it needs no plan.
- Add the outcome `PremiseFailed` to `src/devops_cli/roadmap/stage.py`. `_Planner.plan` returns it for a reply with `premise_failed`; `plan_stage` keeps it in `StagePlan.returned`; `apply_stage` calls `plan_return` and `apply_return` of `src/devops_cli/roadmap/return_item.py` in the round that holds the store. The item gets the evidence as a comment and the Status New, and gets no branch and no pull request.
- Count the item under the new result `returned` of `devops_cli_roadmap_stage_total`, list it in the report of the command, and give it the outcome `returned` in the live run of the golden set (`src/devops_cli/roadmap/stage_eval_run.py`).
- Ask `feasibility` to quote the probe text, and tell the model when to set `premise_failed`, in `src/devops_cli/ai/tasks/roadmap_stage_change.md`.
- Remove `FALSE_PREMISE` from `PENDING_GATES` in `src/devops_cli/roadmap/stage_eval_gates.py` and set the gate of its recorded defects to `none` (see the design).
- Add the constants of the bound to `src/devops_cli/config/constants.py` and the texts to `src/devops_cli/lang/en/messages.py`.
- Update `docs/TELEMETRY.md` and the description of the counter in `src/devops_cli/telemetry/instruments.py` for the result `returned`.
- Spec delta: `roadmap-stage` adds four requirements and modifies the counter requirement. `roadmap-stage-eval` modifies the requirement about a pending defect, since the list of its types changes. The change observes a new behavior of the job, so it carries a delta.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: The job probes the premise at the staging commit, The probes are bounded and read-only, A false premise returns the item, The prompt asks feasibility to quote the probes, Each item of a stage round counts once by its result
- `roadmap-stage-eval`: A defect for a gate that does not exist yet is listed, not failed

## Impact

- Code: `src/devops_cli/roadmap/stage_probe.py` (new), `src/devops_cli/roadmap/refine.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_eval_gates.py`, `src/devops_cli/roadmap/stage_eval_run.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/telemetry/instruments.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `docs/TELEMETRY.md`
- Tests: `tests/roadmap/test_roadmap_stage_probe.py` (new), `tests/roadmap/test_roadmap_stage_plan.py`, `tests/roadmap/test_roadmap_stage_apply.py`, `tests/roadmap/test_roadmap_stage_job.py`, `tests/roadmap/test_roadmap_stage_command.py`, `tests/roadmap/test_roadmap_stage_kind.py`, `tests/roadmap/test_roadmap_stage_eval_run.py`, `tests/roadmap/test_roadmap_stage_eval_gates.py`
- Data: the `case.json` files of `tests/fixtures/roadmap_eval/stage/` that record a `false_premise` defect

## Feasibility

Checked on 2026-11-02 against `origin/main` at `6f648d59` (git 2.43.0):

- `git grep -n "premise_failed" origin/main -- src` prints nothing, so the field and its handling are new.
- `git cat-file -e origin/main:src/devops_cli/roadmap/stage_probe.py` exits 128, so the module is new.
- `git grep -n -w "validate_url" origin/main -- '*.py'` prints only a comment of `tests/http/test_http_egress.py`, and `git log -n3 -S validate_url --format='%h %as %s' origin/main -- '*.py'` prints `36da9390 2026-11-01 docs(openspec): fix plan #2585 real test paths and spec delta (#3083)`. This is the probe of the #2971 replay: the identifier has no definition, and a commit is found that touched the text. The replay test builds the same history in a temporary repository.
- `git grep -n "plan_return" origin/main -- src` prints `src/devops_cli/roadmap/return_item.py:34` and its use in `src/devops_cli/commands/roadmap.py:859`. The job can return an item in process with `plan_return` and `apply_return(store, plan)`. `_Planner` holds no store and `plan()` returns `StagedChange | OverBudget`, so the return needs a third outcome and the round that holds the store makes the writes, as `_stop_on_budget` does.
- Overlap with existing code. `collect_context` (`src/devops_cli/roadmap/refine.py`) already extracts the backtick-quoted paths and identifiers and reads them at the staging commit, and #3012 added the tests and callers of each symbol. It reports only what exists: for a missing path or identifier the model sees nothing, and cannot tell a thing that was removed from a thing that the issue asks to create. The read-only toolbox (`git_log`, `git_show`, `search_code`, `callers` in `src/devops_cli/roadmap/stage_tools.py`) can answer this question, but the model must choose to ask, and nothing makes it ask. The change adds only the missing facts (existence, definition, removal commit) and the return of the item. It reuses the extraction.
- Overlap with #3153. The verification pass of `src/devops_cli/roadmap/stage_verify.py` (merged) runs after the plan and the checks, with a model that reads the plan and the start of each file the plan cites. A `false_premise` finding with a quote that is in its input returns the plan to the planner once. It never returns the item, it does not read the issue's cited identifiers against the history, and it costs two model calls for each item. This change runs before the model call, with no model, and returns the item. The two fit: a plan that comes back from the pass may also answer with `premise_failed`, and the job returns the item then. The change keeps to what #3153 lacks: the facts about the history, and the return.
- First checks of the implementation: `uv run devops ci test tests/roadmap/test_roadmap_stage_probe.py` for the probe, and `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` for the model input and the return.

## Existing Tool Considered

The probes are standard git commands (`git cat-file -e`, `git grep`, `git log --diff-filter=DR`, `git log -S`) run through the `git` helper that `refine.py` already uses, and the extraction is the one of `collect_context`. No library covers the need: `git` is the tool. The change builds about 600 lines of Python, prompt text, fixtures and tests: about 12,000 tokens to build, keep and fix, and about 2 hours of elapsed agent time. It deletes the private `_git` name and the `FALSE_PREMISE` entry of `PENDING_GATES`.
