# Proposal

## Why

Issue #3483: an item can wait in refine after the cause of its wait ended. Refine reads a stage return as the act of a person, so a New item with `refine.next_step` `ready` and a stage return waits for a reason that no person owes. A wait on a person ignores the issues and files that its own text names, so it stays after those issues closed or those files changed. A person wait has no line in `devops roadmap inbox` and no reason in `devops roadmap explain`.

## What Changes

- A stage return after refine's last comment is the act of a job. The next round refines the item again with no reply and no body edit. The model reads the evidence of the return in the request key `stage_return`.
- A new record key `refine.returned_body_hash` holds the body hash of a round that looked again after a return. A second return on that body waits on a person with a stated reason, and no new look follows.
- The text of the last refine comment on a person wait names issues and files. The wait ends when a named issue closed, or a named file changed, after that comment. The named files need not be in `refine.block_paths`. A round reads at most `CONST_ROADMAP_REFINE_MAX_WAIT_CHECKS` issues and as many files from one text.
- `devops roadmap explain <issue>` adds a `Refine job` line: yes, or no with the wait of the item.
- `devops roadmap inbox` adds one line for each open New item that waits on a person in refine.
- The dry-run plans of `refine` and `explain` list the new reads.
- The change alters devops commands and messages, so it carries a spec delta: five ADDED requirements in `roadmap-refine`, one MODIFIED requirement in `roadmap-explain`, and one MODIFIED and one ADDED requirement in `roadmap-inbox`.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `roadmap-refine`: a stage return and a closed or changed cause end a wait.
- `roadmap-explain`: the refine job has a verdict.
- `roadmap-inbox`: a refine wait on a person has a line.

## Impact

- `src/devops_cli/roadmap/refine.py`, `store.py`, `inbox.py`, `explain.py`, `request_plan.py`.
- `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`.
- `src/devops_cli/ai/tasks/roadmap_refine_proposal.md`, `roadmap_refine_investigation.md`.
- `tests/roadmap/test_roadmap_refine.py`, `test_roadmap_inbox.py`, `test_roadmap_explain.py`.
- `docs/roadmap/refine.md`, `docs/roadmap/inbox.md`, `docs/ROADMAP_WORKFLOW.md`, generated command reference.

## Feasibility

- The code of `_still_waiting` in `src/devops_cli/roadmap/refine.py` confirms the premise. The case `NextStep.READY` always sets `refine_set_back_by_person`. `replies_since_refine` drops the comments of other jobs, so a stage return counts as no reply. `_replies_for_model` drops them too, so the model never reads the stage evidence.
- The comment of the stage job carries `CONST_ROADMAP_STAGE_COMMENT_MARKER`. The job returns an item with no branch and no pull request, so a stage comment on an item with no `stage.branch` is a return. A staged item holds `stage.branch`, so its comments are no return.
- `RoadmapStore.closures` gives the close events of an issue, and `RoadmapStore.path_changed_at` gives the newest commit of a path. Both exist in the in-memory store and the GitHub store, so a test runs offline.
- The cap of 2 comments in 24 hours (#2475) still holds. A return gives one new look, which is the second comment of refine in the window. A third look inside the window waits for the cap.
- The criterion "one bounded new look covers the waits recorded before the current analysis model" needs the model of #3478 to run first. That model writes stubs for some replies now. A run of it on 20 real waits would write those stubs to 20 issues. A read of the repository on 2026-11-04 (no model, no write) applied the rules to the New items with an unchanged body: of 75 waits on a person, 12 more reopen than before (#1314 among them), and of 31 returns of the stage job, 29 more reopen. The model run is left to a person after #3478 merges.

## Existing Tool Considered

Existing project code covers the facts: `_is_open`, `RoadmapStore.closures`, `RoadmapStore.path_changed_at`, `CONST_ROADMAP_JOB_COMMENT_MARKERS` and the cited-path pattern of `refine.py`. The change adds no library and no new helper beyond two small readers of issue numbers and paths in a text.
