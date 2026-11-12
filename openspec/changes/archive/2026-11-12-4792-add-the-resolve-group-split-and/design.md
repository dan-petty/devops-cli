# Design

## Decisions

The decisions are in ADR 0021 section 8, ADR 0022 section 2 and the catalogue of ADR 0020. In short:

- **Amend in place.** The three records get the rows in their own lists, and a Status paragraph that names #4792. A new ADR would add a title, a status note and options to the ADR budget of the alternatives check, which has 9 tokens left (#5049).
- **One section for the new rows.** ADR 0021 section 8 gives the shared rules, and for each row the selection, the trigger, the bounds, the marker, the record keys, the idempotency key and the Valkey keys. The unit table points to it.
- **`watch` is a step of the sweep.** It replaces `stage_ready` and `pr_conflicts`. Until the sweep step (#4574), it is a row of the status lane.
- **`fix-checks` and `fix-conflict` are units that the sweep creates** from a due mark that `watch` sets. So the rule "Only the router and the sweep create units" stays.
- **`push` and `open` are steps** inside the unit of their producer, not units.
- **The trigger transport stays** due marks and the sweep. No Valkey stream is a trigger queue, and no dispatcher exists.
- **Argo Events stays rejected** with the corrected upstream facts and three revisit conditions.
- **Row names** have 12 characters or fewer and are never `repair`.
- **Glossary.** "Step" already means the work of one task group. The new terms are "Roadmap step" (the command group `devops roadmap step`) and "Step job", so one word keeps one meaning.

## Rejected alternatives

- **A new ADR 0026 that amends ADR 0020, ADR 0021 and ADR 0022.** It adds about 300 tokens to the ADR budget, so the alternatives check leaves out ADR 0001. The issue also asks to amend the three records.
- **Status notes at the top of the amended records.** A top note that names no ADR ends the status that the alternatives check reads, and a note that names an ADR adds tokens.
- **A new marker for `watch` that reuses `pr_conflicts`.** The row name changes, so the marker follows the row. The item that builds `watch` (#5024) handles the comments that hold the old marker.
- **The fix spend in this record as approved.** The spend of the fix units is a separate owner decision on tracker #5014. The rows start in mode `plan`.
- **A spec delta for the rows.** The rows are not built. A requirement now describes behavior that the code does not have. Each item adds its own delta.
