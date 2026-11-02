# Proposal

## Why

Issue #2423: refine holds a whole item when one part of it cannot be built as written, or when one question needs a person. The item waits on a person (`NextStep.PERSON`) or on a block (`NextStep.BLOCKED`). The part that is ready to build waits with it.

The change lets refine take the unworkable part out of the proposal and file it as new items. The rest of the item can then reach Ready.

## What Changes

- The refine reply gains the key `deferred`: at most 3 parts, each with a `title` and a `body`. The prompts tell the model when to use it. The proposal then covers only the workable scope.
- `split_offs`, `fits_one_pr` and `NextStep.SPLIT` stay. They serve an item that is too big for one pull request, where a person splits the work. `deferred` serves a part that cannot be built or decided now, and it never blocks Ready.
- Refine plans the new items only when the item is Ready. For each part, refine makes an intake plan with `plan_intake`. A part that intake cannot place keeps the item New, and the next step is a person.
- On `--confirm`, refine files the parts first, with `apply_intake`. Then it writes the section and sets Ready. A new issue body starts with `Split from #<issue>.`.
- The link is the body line, one sentence in the existing Ready comment of the item, and the job record key `refine.deferred`. Refine does not link a sub-issue, because an issue with a sub-issue is a tracker and the stage job leaves a tracker out (see design.md).
- A part that an earlier round filed is not filed again.
- `devops roadmap refine --dry-run` lists the requests of one deferred part.
- The change is observable (a command, its model reply and its comment), so it carries a delta in `roadmap-refine`.
- The change fits one pull request. It has 5 task groups.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-refine`: ADDED requirements for the `deferred` key, the filing of the parts, the links, the refusal of a part, the repeat round and the dry run. No existing requirement changes.

## Impact

- Code: `src/devops_cli/roadmap/refine.py`, `src/devops_cli/roadmap/store.py` (the key `RefineRecordKey.DEFERRED`), `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`.
- Prompts: `src/devops_cli/ai/tasks/roadmap_refine_proposal.md`, `src/devops_cli/ai/tasks/roadmap_refine_reply.md`. The investigation prompt `roadmap_refine_investigation.md` needs no edit: it sends back the whole proposal and the reply prompt is appended to it.
- Documents: `docs/ROADMAP_WORKFLOW.md` (the key `refine.deferred` and the refine step) and the generated command documents.
- Tests: new `tests/roadmap/test_roadmap_refine_deferred.py`; extended `tests/roadmap/test_roadmap_refine.py` (the prompt pin test) and `tests/roadmap/test_roadmap_dry_runs.py`.
- Existing code the change reuses: `plan_intake`, `apply_intake`, `NewCandidate` (`src/devops_cli/roadmap/intake.py`), `build_intake_model` (`src/devops_cli/roadmap/intake_model.py`), `sanitize_text`, `step_comment`, `check_ready` and `apply_refine` (`src/devops_cli/roadmap/refine.py`), `StoreRequests` and `planned_requests` (`src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/roadmap/intake_requests.py`).
- Existing tests that must keep passing: the split tests of `tests/roadmap/test_roadmap_refine.py` (`test_too_big_needs_split`, the `_SPLIT` cases), `tests/roadmap/test_roadmap_stage_selection.py` (a tracker is left out), `tests/invariants/test_roadmap_workflow_doc.py` (each record key is in the document) and `tests/roadmap/test_roadmap_dry_runs.py`.
- Existing spec requirements that must keep holding: "Only a person's decision or an unsourced fact waits on a person", "Refine writes at most two comments on one item in a day" (the change adds no comment) and "The hash of the body leaves out the job's block".
- Deleted code: none.

## Acceptance

The issue lists 5 criteria. Each maps to a group of `tasks.md`.

- Criterion 1, the refine prompt tells the model to take out unworkable scope: group 1 (prompts and reply key) and group 2 (the already-filed parts in the request).
- Criterion 2, the orchestrator creates a new issue for each part: group 2 (plan) and group 3 (file). Group 4 adds the dry-run requests.
- Criterion 3, the remaining scope proceeds to Ready: group 2 (Ready is decided on the proposal without the parts) and group 3 (the status write after the filing).
- Criterion 4, links between the original and the new issues: group 3 (body line, comment, record key).
- Criterion 5, tests cover the splitting: every behavior group starts with its failing tests (groups 1 to 4).
- The verification step of criteria 2 and 3 in the issue is a run on a test issue. Tests with `InMemoryRoadmapStore` give the same answer each time. The live run is pending a person (see `tasks.md`).

## Feasibility

Checked on 2026-11-01 in a worktree at `origin/main` (1c20865a).

- The reply schema refuses `deferred` today.
  `RefinementProposal.model_validate({'problem_statement': 'p', 'existing_tool': 't', 'deferred': [{'title': 'a', 'body': 'b'}]})` raises `ValidationError ... Extra inputs are not permitted [type=extra_forbidden`. `class RefinementProposal(BaseModel)` has `model_config = ConfigDict(extra="forbid")` (`src/devops_cli/roadmap/refine.py:198-200`). So the key must be added to the model and to `roadmap_refine_reply.md`, which says "The reply has these keys and no other".
- Nothing newer did this work. `git grep -n -i "deferred" -- src/devops_cli/roadmap` prints nothing. `git log --since=2026-10-20 -- src/devops_cli/roadmap/refine.py` shows #2784, #2691, #2688, #2686, #2681 and #2591 and no change to scope splitting. The search of issues for "refine split" (`search/issues`, 30 results) finds no other issue about scope splitting in refine. The issue was created on 2026-10-28.
- The current mechanism is a different case. `check_ready` returns false when `not proposal.fits_one_pr` (`refine.py:957`). `next_step_of` returns `NextStep.SPLIT, tuple(proposal.split_offs)` for it (`refine.py:982-983`), and the step comment asks a person to split. A deferred part must not block Ready, so `split_offs` cannot carry it.
- Intake can be called from refine in two halves. `plan_intake(store, *, repo, model, ref, issues, new, limit, waiting)` writes nothing (`intake.py:1167`) and `apply_intake(store, plan)` writes (`intake.py:1298`). `intake_candidate` is these two calls (`intake.py:1338-1362`). Refine has the same plan and apply split (`plan_refine`, `apply_refine`). `plan_intake` needs an `IntakeModel`. `build_intake_model()` makes one (`intake_model.py:241`).
- A sub-issue link would stop the original from being staged. `parent = _source_issue(...)` (`intake.py:1146`) sets a parent when `NewCandidate.source` names an issue of the repository, and `_apply_placement` then calls `store.add_sub_issue(decision.parent, number)` (`intake.py:1272`). `_tracker` in the stage job returns the "left out" reason when `item.sub_issues > 0` (`stage.py:351`), and `tests/roadmap/test_roadmap_stage_selection.py::test_a_tracker_is_left_out_under_the_wide_default_filter` pins it. So refine must pass no `source`.
- The refine comment cap holds. `CONST_ROADMAP_REFINE_MAX_COMMENTS_PER_ITEM` is 2 (`src/devops_cli/config/constants.py:2942`). The change adds a sentence to the Ready comment that refine already writes, so it adds no comment.
- The investigation keeps the field. `_investigate` sends `first.model_dump(mode="json")` and the investigation prompt says "Reply with the whole proposal ... Keep each part that the evidence does not change" (`refine.py:1766`, `roadmap_refine_investigation.md`). `validate_proposal` builds its result with `proposal.model_copy(...)` (`refine.py:913`), which keeps a new field.
- Issue #2423 is not a duplicate of #2398. #2398 (merged) made refine investigate open questions with tools. A question that stays open after the investigation, or a block, is what #2423 moves out.

## Existing Tool Considered

No open tool splits an issue by the judgement of a model. GitHub sub-issues link issues, and they make the parent a tracker that the stage job leaves out (see Feasibility), so they cannot carry the split. The change reuses the intake of this repository for the filing and the reply schema of refine for the model, and it adds no dependency.

Cost of building the change (estimates, in the units that AGENTS.md rule 3 asks for): about 160,000 input tokens to build (4 behavior groups near the 40,000-token budget, and one document group), about 600 lines of code and tests to keep, and about 40,000 tokens a year to fix (one group of the same size when the intake or the reply schema changes). The elapsed time is about 2 hours of Job time.
