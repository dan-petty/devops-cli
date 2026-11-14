# Design

## Decisions

**The plan text goes above `Plans`, as the delivery text goes above `Closes`.** CONTRIBUTING.md already says that `Plans` takes the place of `Closes`, so a reader who writes the text first is right. The form follows the document.

**The short message names the line that the text goes above.** A plan writer reads `Plans` and the direction in one message, and a delivery writer still reads `Closes`. `_text_problems` takes the message of its caller.

**The builder writes the same order that the form reads.** `build_plan_body` writes `why`, then `Plans`, then `Change:`, so the service's draft and the check cannot drift.

## Rejected alternatives

- **Accept both orders.** Two accepted orders leave the document ambiguous and let a body put a closing keyword near the text.
- **Refuse the old order with a message only.** The document and the form would still disagree, which is the issue.
