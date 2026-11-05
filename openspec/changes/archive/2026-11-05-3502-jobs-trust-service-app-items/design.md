# Design

## Context

The jobs read an item through `Item`, and decided its trust with `author_association` and `CONST_ROADMAP_TRUSTED_AUTHORS` in four places. The Service App and `github-actions[bot]` open items, and GitHub gives them CONTRIBUTOR. See proposal.md for the numbers and the owner decision.

## Goals / Non-Goals

**Goals:**

- The four readers trust one rule, in one module.
- An item of a bot reaches Ready only after a review, and the other jobs take it only with a recorded approval.
- Text from an outside account does not reach the model of refine, or the model of the alternatives job, as a reply.
- An approval holds only for the body that the review read.
- The author of an item that the jobs do not trust gets one comment.

**Non-Goals:**

- The retry right of `implement: retry`. It keeps the association test, so a bot gains no retry right.
- The `trusted` test of intake. It also reads the `source/agent` label.
- A change to the prompt of the review or to its golden set.

## Decisions

- **One module, `trust.py`.** `is_trusted`, `is_bot_filed`, `is_approved` and `trusted_replies` are the only code that compares an author. The readers differ only in the reason text that they give.
  - Rejected: a field `trusted` on `Item`. The rule reads the settings, and the store has no settings.
- **The login is the proof.** The jobs compare the author login with `bot_login()` by equality, and with `CONST_ROADMAP_ACTIONS_BOT_LOGIN`. GitHub gives both bots the association CONTRIBUTOR, as the evidence in proposal.md shows.
  - Rejected: trust any author of type Bot. It trusts bots outside the project's control.
  - Rejected: trust the association CONTRIBUTOR. It also holds each person whose commit was merged, with no write access.
  - Rejected: a prefix or a case-folded match. The `lookalike` tests show the exact match is the only safe one.
- **With no App slug, `bot_login` is None and no item of the App is trusted.** `github-actions[bot]` stays trusted, as the owner decided.
- **Item, IssueRecord and IssueComment hold `author_login`.** The listings that a round reads already carry `user`, so the check costs no request.
  - Rejected: a read of the author in each reader. It adds a request for each item.
- **The review reuses `stage_verify.verify`.** The owner decided on the verification pass and the slot `ai.tasks.verification`, with no new model and no new tool. The proposal goes in as the `plan`, and `open_findings` decides the refusal: a type that keeps a plan in draft, with a quote that is in the input.
  - Rejected: a new prompt for the proposal. It needs its own golden set and its own scoring, and the owner asked for no new tool.
  - Rejected: a refusal on any finding. A finding with no quote that the input holds is advice in the stage job, and it stays advice here.
- **A refusal is `NextStep.EDIT`.** The step already means "waits on a body edit alone", so the item is not refined again, and the review is not called again, until the body changes. The comment uses `step_comment` with a new `edit` text, which lists each finding with its evidence. The refusal comment carries refine's marker, so the cap of two comments in 24 hours counts it.
  - Rejected: `NextStep.PERSON`. A reply would end the wait, and a bot reply would loop the review.
- **The approval is the record key `refine.judge`, and it holds only for the body that the review read.** The verdict is written in the same call that records `refine.body_hash` and `refine.section_hash`. A round that does not review the item clears it. `is_approved` is true only when the verdict is `approved` and the body hashes as those two keys record. A round that looks again at an item with a valid approval keeps it with no model call.
  - Rejected: a label. A job record is where the other jobs already read what refine decided.
  - Rejected: the verdict alone, with the next round as the check of the body. The owner asked on #3502 for the check of the edit of a body after the approval. A probe with the in-memory store showed that the stage job took an item on the old approval after a body edit. So the approval is bound to the hashes.
  - The hashes move to `body_hash.py`, so `trust.py` can read them with no import of `refine.py`, which imports `trust.py`.
  - A write of the hashes with no review also clears the verdict. These writes are the record of an item that is too big to refine, and of an item whose model call failed twice on its own text. Without the clear, the hashes would belong to a body that no review read.
  - The title is no part of the hashes. Refine itself ignores a retitle, and the review does not read a part of the item that a round looks at again.
- **A round looks again at a Ready item of a bot with no valid approval.** Without it, a body edit would leave the item out of the stage job with no way back. `_refinable` takes such an item. The review runs. The item then stays Ready with a new approval, or goes back to New with the step `edit`, as any Ready item that refine finds not ready.
- **The review runs before the intake plan of the deferred parts.** A refusal then costs no intake call.
- **The comments that reach the models are those of trusted authors**: a person with write access, or the App's bot. `github-actions[bot]` is an author of items, not of replies. `_Selection.comments_on` and `refine_one_item` filter at the one read, so the replies, the `covers` answers, the stage return and the wait checks all see the same comments. The alternatives job filters the comments that it gives to its model with the same function. It filters before it looks for its own marker, so an outside comment that holds the marker moves no window. The in-memory store gives the owner's association to a comment that it writes or seeds with no association, as GitHub gives an association to each comment.
  - Rejected: keep every comment and trust a split-off only when every reply came from a trusted author. Outside text would still reach the model.
- **The comment to the author is written by apply, and found by the selection.** The selection reads the comments of an item that the jobs do not trust, and sets `notice` when no comment holds the marker. A round that finds `notice` writes the comment, and the plan has writes. Only refine writes it: stage, implement and alternatives are read-only selections whose left-out reasons show in their reports.
  - Rejected: a mark in the job record. An item of an outside account has no record, and a body write to its issue is more invasive than a comment.
  - Rejected: a count in process memory. A new round or another process writes a second comment.
- **`refine.py` imports `refine_judge` in the function.** `stage_verify` imports `stage_change`, which imports `refine`.

## Risks / Trade-offs

- [The review sees no file, so it finds fewer defects than the stage review] → the review is no security control. The login and the reply filter are the controls, and a person still merges each pull request.
- [An item of `github-actions[bot]` can carry text from a workflow input] → the owner accepted this in the decision on #3502. The filter keeps outside replies away from the model, and SECURITY.md names the risk.
- [A bot-filed item approved by the review, then edited by a person] → the approval ends at once. The next round reviews the new body. Until then no job takes the item.
- [The approval is a block in the issue body, so text that a bot copies into the body could forge it] → the audit workflow writes a fixed text, and refine neutralizes `<!` in the text that it files for the Service (#2478). SECURITY.md names the risk for a new workflow.
- [A round reads the comments of each item that the jobs do not trust] → the set is small once the bots are trusted. The dry-run plan lists that read and the comment that follows.
- [A Ready item of a bot that was refined before this change has no verdict] → one round reviews it. An approval then lets the stage job take it, and a refusal sets it back to New.
