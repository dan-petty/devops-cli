# Proposal

## Why

The review of refine (#3502) refuses a Ready proposal for an item that a bot opened, and the item then waits for a person to edit the body (#4798). The census of 2026-11-11 found 36 bot items with a verdict of the review: 8 approved and 28 refused. All 28 refused items were New with the step `edit`. Their median time in the Status was 6.0 days, and 25 of them had no free comment. The owner rule of 2026-11-05 says that bot-filed work goes on with an agentic judge and no person, and the owner accepted the agent round on 2026-11-11 (#4780). A refusal is a defect of the proposal, which the next proposal can fix. This change routes a refusal to a job failure of refine, so that the next round refines the item again with the findings.

## What Changes

- A refusal of the review is a job failure with the new check `judge_refused` (`JobCheck.JUDGE_REFUSED`). It counts in `refine.tries` on the same body, as the other job failures do. The step is `retry` below 3 tries (`CONST_ROADMAP_REFINE_MAX_TRIES`) and `failed` at the limit. `devops roadmap inbox` lists a `failed` item in its class `failed`.
- The job record keeps each open finding with its evidence in the new key `refine.judge_findings`, at most `CONST_ROADMAP_REFINE_JUDGE_FINDINGS_MAX_CHARS` (2,000) characters. `refine.failure` holds the first finding. A round that does not fail clears the key.
- The request of the proposal step and of the investigation has the new key `judge_findings`. The prompt `roadmap_refine_proposal.md` tells the model to fix each finding or take out the claim.
- A refusal writes the body with the section of the refused proposal and sets a Ready item back to New, as before. It writes no comment. The text of the comment that asked a person for a body edit (`refine_step_comments["edit"]`) is deleted.
- An item of a person gets no review, so its behavior does not change.
- The change carries a spec delta: the job record, the next step and the comment are observable.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-refine`: A refusal of the review is a job failure that a later round fixes, The review keeps the approval of an unchanged body, A round reviews a Ready item of a bot again when its approval ends, A passing proposal clears the job failure. Two requirements go: A refusal keeps the item New and lists each finding, The review looks again only after the body changes.

## Impact

- Code: `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/refine/refine_judge.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/ai/tasks/roadmap_refine_proposal.md`, `src/devops_cli/ai/tasks/roadmap_refine_investigation.md`
- Documents: `docs/roadmap/refine.md`, `docs/ROADMAP_WORKFLOW.md`
- Tests: `tests/roadmap/refine/test_roadmap_refine_trust.py`, `tests/roadmap/test_roadmap_limit_classes.py`
- The items that a refusal left with the step `edit` before this change keep that wait. One `devops roadmap refine --item <number> --confirm` round for each item puts it on the new route.

## Feasibility

- `src/devops_cli/roadmap/refine/refine.py` at `origin/main` (bbb952ed, 2026-11-11) confirms the cause. In `refine_one_item`, a refusal sets `NextStep.EDIT` with the findings as the details of the comment. `_still_waiting` treats `EDIT` as a wait that only a body edit ends, so the next round makes no model call.
- The same file holds the job failure of #3632: `_failed_round` counts `refine.tries` on the body, `RETRY` is no wait, and `FAILED` at 3 tries waits on a body edit. `inbox.py` lists `FAILED` in the class `failed`. So the route exists, and the refusal only needs to join it.
- The census of 2026-11-11T17:30Z (the job records of 437 open issues) gives the counts in Why: `refine.judge` is `refused` on 28 records (20 of the Service App, 8 of `github-actions[bot]`) and `approved` on 8. Each refused record holds `refine.next_step` `edit`.
- The question resolver of #4780 is not built: no module of `src/` names it. Its answers become an input of refine in a later item of #4780, which adds them to the check for an unchanged item. This change does not add that input.

## Existing Tool Considered

The refine agent, the verification pass of the stage job (#3502) and the job failure of refine (#3632) cover each part. No outside tool routes a refusal of a review in a roadmap job. The change joins these parts. Cost to build: about 80,000 tokens and 2 hours, as the issue states. Code that the change deletes: the `edit` text of `refine_step_comments` and the branch of `refine_one_item` that gave a refusal the step `edit`.
