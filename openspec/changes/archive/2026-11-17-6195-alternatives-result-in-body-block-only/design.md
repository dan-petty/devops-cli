# Design

## Decisions
- **The block is the result, the comment is the event.** The body block holds what is true now. The comment says that the result changed, what it was before, and gives the evidence of that run. A recheck with the same result writes only the block, as before (#4054).
- **The result before the check comes from the job record.** `alternatives.verdict` and `alternatives.tool` of the item as the run read it give the earlier result. A first check names no check. `_result_changed` reads the same keys, so the line and the gate agree.
- **The sentence about a person stays.** The footer said that a person decides what the check means for the item. It is now the end of the one line of the change, so no text is lost and the comment has no date that the block also holds.
- **The block has blank lines between its parts.** GitHub reads a line after a list item as a part of that item, so `Covers:` and `Lacks:` are each a paragraph. Every reader of the block reads it whole or leaves it out, so no reader parses a line.
- **Refine keeps the record keys.** The request keeps `verdict` and `tool`: the prompt uses them to choose what to do (a `covers` question, a `rejected` ADR). The block holds the rest of the result.
- **Refine reads the whole comment.** The comment is now the evidence only, and the owner rule of 2026-11-17 refuses a cut that drops context.
- **Intake compares the text of a person.** `text_of_a_person` leaves out the block and the refine section, as the consolidation job does. The candidate still goes through the same shortlist and verdict, so a possible duplicate is still flagged.
- **The dry-run plan states the skip class as a condition.** A dry run makes no request, so it cannot know the class of an item. The comment carries the condition that the item is no skip class.

## Rejected alternatives
- **Keep a short comment for a skip class**: the comment repeats the class and the verdict of the block, and a skip class has no evidence. The live census of #6193 shows the 6 `not-applicable` comments are 99% body text.
- **Move the evidence into the block too**: the body would grow by the sources and searches of each run, and stage and refine read the body under a cap. The evidence belongs to one run, so the comment of that run holds it.
- **Remove `verdict` and `tool` from the refine request**: the prompt branches on them, and the model would have to parse them from the text of the block.
- **Cut the comment at a larger cap**: the owner refused hard caps that drop context (2026-11-17).
- **Compare raw bodies in intake and filter the block in the embedder**: `text_of_a_person` already does this for the consolidation job, so a second filter would be a second rule for the same text.
