# Design

## Context

The job (#2650) writes three records on an item: a block in the body, `alternatives.*` keys in the job record, and a comment. Refine plans an item from its body, its replies and the repository. The Service runs one table of rows for each lane. This change joins the two: the row runs the job daily, and refine plans with the verdict.

## Decisions

- **One row, the job's own functions.** The runner calls `plan_alternatives`, `apply_alternatives` and `raise_for_failed_checks`, as `_run_refine_adapter` calls the functions of refine. A failed check fails the row after the others are written, so the ledger of failed rounds counts it as it counts a failed refine item. A row needs no clone, so `needs_clone` stays False.
- **The limit is a setting.** `roadmap.alternatives.limit` (default `DEFAULT_ROADMAP_ALTERNATIVES_LIMIT`) is the one source of the limit for the row and for the command. The command's `--limit` has no default of its own: when it is not given, the setting applies.
- **The row is due by interval only.** It has no `batch_keys` and no due rule. A webhook hint makes no check due, because the job's own selection decides which items need a check: an item with no check, an old check, or a changed body.
- **The verdict is read from the record, the question is built by the code.** Refine takes the verdict and the tool from the job record, and requires the job's block in the body. A block that a person deleted is no check. The `covers` question is deterministic text from a message template, not model text, so a model cannot drop it or change it. The request also holds the block and the job's latest comment (cut to a token cap), so the proposal can name what the tool lacks: the comment holds the lists, the block does not.
- **The question closes by a person's reply and by the proposal.** While no person has replied after the job's latest comment, the question is added to the open questions as a question for a person, and the model cannot answer it. After a reply, the question joins the numbered key questions of the request, and it is open until an answer names its number, as for any key question of the body. A comment of refine or of the job is no reply.
- **Second look by the record.** Selection judges an item by its listing, with no comment read (#1539). `refine.alternatives_asked` holds the URL of the covering tool that the last round put to a person. An item whose record holds a covering tool that differs from it is selected, even when the body is unchanged and even when it is Ready. The round writes the new URL. A re-check that finds the same tool changes nothing, so an answered item is not thrown back to New every 30 days.
- **The hash of the body leaves out the job's block.** `body_hash` is the hash that `_is_unchanged` compares: the body outside the block and the refine section. The check before a write compares a different hash, of the whole body outside the refine section, so a block that the job wrote after refine read the body is not lost by the write. Both hashes are fields of the refined item.
- **The metric is counted at the write.** `devops_cli_roadmap_alternatives_total{verdict}` counts a check when the job writes it, so a plan that is not applied, and a check that is skipped because the body changed, count nothing. A skipped item has no verdict.
- **`Verdict` lives in the store module.** The record keys that hold its values are there. Refine imports the store already, and the job imports refine, so the enum cannot stay in the job. `alternatives.py` keeps the name in its exports.

## Rejected alternatives

- **Let the model decide if a `covers` verdict is a question.** A model can drop it. The deterministic question keeps the rule (a covering tool is a decision of a person), as the issue states. Rejected.
- **Read the verdict by parsing the block or the comment.** It needs hand-written text parsing of text that the job writes itself. The record holds the same values as fields. Rejected.
- **A due rule or a webhook batch key for the row.** The job's selection already finds the items that need a check, and a check costs model calls and searches. Webhook hints would run it at each edit. Rejected.
- **Select Ready items by a read of their comments.** It costs one comment read for each Ready item in every round, which #1539 removed. The job record costs nothing. Rejected.
- **Record the time of the check as the second-look key.** A re-check of the same tool every 30 days would throw an answered, Ready item back to New and ask again. The tool URL asks again only when the tool is new. Rejected.
- **A project-board field for the question.** ADR 0016 keeps the board out of every job. Rejected.
- **A new capability spec.** The Service row belongs to the job's capability and the question belongs to refine's. Both exist, so the deltas ADD requirements to them. Rejected.

## Known limit

A re-check of the job posts a new comment. If refine runs the item again later (a body edit, for example) and no person replied after that newest comment, a `covers` question that a person answered earlier is open again. The person answers it with one reply.
