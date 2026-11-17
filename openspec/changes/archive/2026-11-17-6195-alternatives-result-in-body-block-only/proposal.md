# Proposal: #6195

## Why
#6195 is area 2 of #6193. The owner rule of #6193: no job posts the same content to an issue twice, and content in the body of an issue is not in a comment too. The alternatives job breaks it:

- `_block_of` writes the verdict, the skip class, `_basis` and `_tool_line` to the body block. `_comment_of` writes the same `_basis` and `_tool_line` to the comment. A skip-class comment only repeats the verdict and the class of the block.
- Refine sends the record verdict and tool, the block and the comment, so its model gets these facts three times. Refine also cuts the comment to `CONST_ROADMAP_REFINE_MAX_REPLY_TOKENS`, against the owner rule of 2026-11-17 on hard caps.
- Live: 22 of 22 sampled alternatives comments repeat the block. The 6 `not-applicable` comments are 99% body text (1,554 of 1,788 B).

## What Changes
- The body block holds the current result: the date, the verdict, the skip class, the basis, the tool line, the model reason, `Covers:` and `Lacks:`.
- The comment is an event. It posts only when `_result_changed` is true, for an item that is no skip class. It holds the marker, one line that says the result in the block changed and what the record held before, and the folded evidence of the run: the tools considered, the searches with their result counts and every source. It repeats no line of the block. The footer sentence is now a part of that one line.
- A skip-class check posts no comment.
- Refine sends the latest alternatives comment whole, with no cut. The block is the source of the reason, the covers and the lacks. An older comment still holds the covers and the lacks, and refine keeps it.
- `roadmap_refine_proposal.md` and `roadmap_refine_investigation.md` name `block` as the source, tell the model to cite the block and not restate it, and tell it not to write that no alternatives check has run when the block holds a result.
- Intake compares the text that a person wrote (`text_of_a_person`), as the consolidation job does, so the bigger block makes no false duplicate flag. A possible duplicate is still flagged.
- The alternatives dry-run plan lists the comment with the condition that the item is no skip class.

The comment, the block, the refine request and the intake comparison are observable, so the change carries spec deltas.

## Capabilities
- `roadmap-alternatives`: the block, the comment, the skip class and the dry-run plan change.
- `roadmap-refine/alternatives`: the request keeps the comment whole, and the prompts name the block as the source.
- `roadmap-intake-duplicates`: intake compares the text that a person wrote.

## Impact
- A typical check (a reason of three sentences, three covers, three lacks, four searches, three sources) has a block of 857 characters (212 tokens) and a comment of 655 characters (170 tokens). Before, the block had 228 characters (62 tokens) and the comment 1,337 characters (342 tokens). The block grows by about 150 tokens, and the comment drops by about 170 tokens.
- The stage job caps the body at `CONST_ROADMAP_STAGE_BODY_MAX_TOKENS`, and the comments take the room under the cap that the body leaves, so the first request does not grow. The stage window test gives the same counts before and after, within the noise of the timestamps of the messages.
- The largest open issue body holds 55,095 characters, under the refine limit `CONST_ROADMAP_REFINE_MAX_BODY_CHARS` of 65,536.
- Old comments stay on GitHub. Refine reads an old comment and a new comment, and the block of each form.
- No setting, no command and no dependency changes. The change fits one pull request.

## Feasibility
- `src/devops_cli/roadmap/alternatives.py` on main: `_comment_of` writes `_basis(check)` and `_tool_line(check.tool)`, and `_block_of` writes the same two; `_result_changed` already gates the comment in `AlternativesWriter.settle`.
- `src/devops_cli/roadmap/refine/refine.py` `_alternatives_request` cuts the comment with `truncate_to_token_limit(..., CONST_ROADMAP_REFINE_MAX_REPLY_TOKENS)`.
- `src/devops_cli/roadmap/intake/intake.py` `_comparison` gives `issue.body` to `_Entry`, whose `text` goes to `embedding_text` and whose `excerpt` goes to the model. `consolidate.py` `_item` uses `text_of_a_person` from `body_hash.py`.
- `src/devops_cli/roadmap/request_plan.py` `alternatives_requests` lists the comment with the condition `check_changed` only.
- Readers of the comment: refine reads the marker and the whole comment; `comment_repeat.py` and `alternatives._request` read the marker only. Readers of the block: refine (`recorded_check`) reads it whole; `body_hash.py` and `_person_text` leave it out. No code parses a line of either.
- `devops gh api repos/dan-petty/devops-cli/issues?state=open` gives 753 open issues; the largest body holds 55,095 characters.

## Existing Tool Considered
The change uses code that the repository holds: `text_of_a_person` from `body_hash.py`, the `<details>` fold of GitHub Markdown, and the builders of the block and the comment. No open tool covers the split of a job's text between an issue body and a comment. The change deletes the skip-class line of the comment, the heading, the tool line and the footer of the comment, and the cut of the comment in refine.
