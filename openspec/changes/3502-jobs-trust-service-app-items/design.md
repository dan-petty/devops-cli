# Design

## Context

The jobs read an item through `Item`, and decided its trust with `author_association` and `CONST_ROADMAP_TRUSTED_AUTHORS` in four places. The Service App and `github-actions[bot]` open items, and GitHub gives them CONTRIBUTOR. See proposal.md for the numbers and the owner decision.

## Goals / Non-Goals

**Goals:**

- The four readers trust one rule, in one module.
- An item of a bot reaches Ready only after a review, and the other jobs take it only with a recorded approval.
- Text from an outside account does not reach the model of refine as a reply.
- The author of an item that the jobs do not trust gets one comment.

**Non-Goals:**

- The retry right of `implement: retry`. It keeps the association test, so a bot gains no retry right.
- The `trusted` test of intake. It also reads the `source/agent` label.
- The comments that the alternatives job gives to its model.
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
- **The approval is the record key `refine.judge`.** The verdict is written in the same call that records the body hash, and a round that does not review the item clears it. A round that looks again at an item that holds the approval and whose body is unchanged keeps it with no model call.
  - Rejected: a label. A job record is where the other jobs already read what refine decided.
  - Rejected: the verdict plus a body hash in the check of the readers. The readers would import the hash of refine. A person who edits the body is a person with write access, so the window between the edit and the next round gives no outside text a path.
- **The review runs before the intake plan of the deferred parts.** A refusal then costs no intake call.
- **The comments that reach the model are those of trusted authors**: a person with write access, or the App's bot. `github-actions[bot]` is an author of items, not of replies. `_Selection.comments_on` and `refine_one_item` filter at the one read, so the replies, the `covers` answers, the stage return and the wait checks all see the same comments. The in-memory store gives the owner's association to a comment that it writes or seeds with no association, as GitHub gives an association to each comment.
  - Rejected: keep every comment and trust a split-off only when every reply came from a trusted author. Outside text would still reach the model.
- **The comment to the author is written by apply, and found by the selection.** The selection reads the comments of an item that the jobs do not trust, and sets `notice` when no comment holds the marker. A round that finds `notice` writes the comment, and the plan has writes. Only refine writes it: stage, implement and alternatives are read-only selections whose left-out reasons show in their reports.
  - Rejected: a mark in the job record. An item of an outside account has no record, and a body write to its issue is more invasive than a comment.
  - Rejected: a count in process memory. A new round or another process writes a second comment.
- **`refine.py` imports `refine_judge` in the function.** `stage_verify` imports `stage_change`, which imports `refine`.

## Risks / Trade-offs

- [The review sees no file, so it finds fewer defects than the stage review] → the review is no security control. The login and the reply filter are the controls, and a person still merges each pull request.
- [An item of `github-actions[bot]` can carry text from a workflow input] → the owner accepted this in the decision on #3502. The filter keeps outside replies away from the model, and SECURITY.md names the risk.
- [A bot-filed item approved by the review, then edited by a person, keeps its approval until the next round] → a person with write access edits it, and the next round looks at the changed body.
- [A round reads the comments of each item that the jobs do not trust] → the set is small once the bots are trusted.
