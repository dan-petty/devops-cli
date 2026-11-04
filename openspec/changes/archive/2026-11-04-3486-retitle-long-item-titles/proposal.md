# Proposal

## Why

Issue #3486: the stage job leaves out an item whose title summary is over 60 characters (`SUMMARY_MAX_CHARS`), and no job shortens that title. On 2026-11-04, 18 of 28 Ready items, 99 of 160 New items and 34 of 53 Planned items were over the limit. A Planned item reached the title check only at the push, after the implement job spent its tokens (#3106 used 580448 input tokens first). A person had to edit each title.

## What Changes

- `devops roadmap intake --title` refuses a new candidate whose summary is over the limit. The message names the length and the limit, and no issue is created. The refusal is in the command, because the review hand-off files titles of up to 200 characters through `intake_candidate`, and `retitle` shortens those.
- New command `devops roadmap retitle` (dry run by default, `--confirm` writes, `--dry-run` makes no request). It shortens the summary of open items and keeps the type and the scope.
  - A Planned item takes the summary of the title of its plan pull request, which `stage.pr` names. The job makes no model call for it. A missing or invalid plan title leaves the item with one comment.
  - Any other item gets one request to the `triage` model, and one more with the faults of the first reply. The job writes only a title that passes `title_problems`.
  - A title that someone changed after the last job comment stays. The job reads the title changes on the timeline of the item.
- `_planned_target` of the implement job leaves out a Planned item with a long summary before it reads the plan or makes a model request. The stage job and the implement job share `long_title_reason`.
- The roadmap store gets `set_title`, `pull_title` and `last_renamed_at`, in the GitHub adapter and in the in-memory adapter.
- The change alters a command, a message and a prompt, so it carries a spec delta: the new capability `roadmap-retitle`.
- This change fits one pull request. The Service row that runs `retitle` on a schedule is not part of it (follow-up #3535).

## Capabilities

### New Capabilities

- `roadmap-retitle`: the repair of long item titles, the intake refusal and the guard of the implement job.

## Impact

- `src/devops_cli/roadmap/retitle.py`, `src/devops_cli/ai/tasks/roadmap_retitle.md`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/roadmap/intake.py`, `stage.py`, `implement.py`, `commit_title.py`, `pull_form.py`.
- `src/devops_cli/roadmap/store.py`, `github_store.py`, `memory_store.py`, `request_plan.py`, `src/devops_cli/lang/en/`, `config/`.
- `docs/roadmap/intake.md`, `docs/roadmap/implement.md`, and the generated command documents.

## Feasibility

- Code at `origin/main` on 2026-11-04: `stage.py` `_Judge._title` leaves out a long summary; `implement.py` `_planned_target` checked only the type; `implement_run.py` checks the title in `_publish`; no job and no intake check shortened or refused a long title.
- GitHub GraphQL `Issue.timelineItems` accepts the item type `RENAMED_TITLE_EVENT` with a `createdAt` field. The REST issues endpoint returns a pull request as an issue with the key `pull_request`, so it gives the title of a merged plan pull request.
- `staging_title` and `StageProposal` bound the plan summary with `STAGE_SUMMARY_MAX_CHARS`, so the summary of a plan pull request title fits. The tests check this with the in-memory store; a run on the live roadmap checks the 34 Planned items.

## Existing Tool Considered

No open, maintained tool shortens a GitHub issue title. `amannn/action-semantic-pull-request` checks a pull request title in CI and cannot rewrite one. The change builds the repair itself: about 60k tokens to build, 20k to keep and fix, and 3 days. It reuses `title_problems`, `build_title`, the GitHub store and the model client, and it deletes no code.
