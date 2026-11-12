# Proposal

## Why

Issue #4799: `devops roadmap repair` listed no item, but the census of 2026-11-11 found 7 items that match its stub rule. The pass took the newest comment of any author as the confirmation. On these items, a comment of another roadmap job came after the question of refine: the alternatives check, the intake reason or a retitle. The pass read that comment as a reply of a person and left the item. The census also found refine sections whose stub text is a word that `is_placeholder` did not know: `ignore`, `pending`, `draft`, `temporary` and "Placeholder not final.".

## What Changes

- The pass reads the newest comment of the job that stalled the item: the stage job for a filler return, refine for a stub refine block. A comment after it is a reply only when it holds no marker of `CONST_ROADMAP_JOB_COMMENT_MARKERS`. The pass uses `replies_after_marker` of refine, the rule that refine uses to find a reply.
- `is_placeholder` knows the census texts `ignore`, `pending`, `draft`, `temporary` and "Placeholder not final." as whole texts. The rule is the one rule of the pull form, so refine, the stage job and the pull request form also refuse these texts.
- The doc page `docs/roadmap/repair.md` states the new rule.

## Capabilities

### Modified Capabilities

- `roadmap-repair`: the pass reads the newest comment of the job and skips the comments of other jobs.
- `roadmap-stage`: the requirement "A placeholder text is one rule" names the census texts.

## Impact

- `src/devops_cli/roadmap/repair.py`, `src/devops_cli/roadmap/pull_form.py`, their tests and `docs/roadmap/repair.md`.
- The live roadmap: the preview lists 14 items, where it listed 0. An agent runs `devops roadmap repair --confirm` after the merge, and refine then reads each item as a new one.
- No new request: the pass reads the same comment listing.

## Feasibility

- `uv run devops roadmap repair` on main printed "No item is stalled by a placeholder reply." on 2026-11-12.
- The comments of #3064, read with `devops gh api repos/dan-petty/devops-cli/issues/3064/comments`, are the intake reason, the refine question and then the alternatives check. The last one is newest, so `_newest` returned it.
- A read-only probe of the 7 census items with the store found Status New, next step `person`, a section with the recorded hash and the text `x` or `placeholder` on 6 of them. #3077 has a real section now and holds Ready.
- The census evidence named 9 more items whose stub text `is_placeholder` did not match.

## Existing Tool Considered

No open tool reads the job markers of this project. The fix reuses `replies_after_marker` of refine and the constant `CONST_ROADMAP_JOB_COMMENT_MARKERS`. Cost: about 30,000 tokens and 1 hour, as the issue states.
