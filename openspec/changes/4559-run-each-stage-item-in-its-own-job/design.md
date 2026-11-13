# Design

## Decisions

- **The Job list is the lock, and the check-out is the claim.** The row lists the stage Jobs of the repository once a round. A running Job holds its item through its item label, whoever started it, and the check-out holds the item between the create and the start of the Job. The selection leaves out an item that either names (`LeftOutKind.STAGE_JOB`), so the walk of the selection is not used up by busy items.
- **Recovery reads the check-out.** Each item whose record holds `stage.job` is compared with the list: a missing Job, a failed Job, a Job past the deadline of the check-out plus 600 s, and a completed Job with a lost check-in. The row checks in for the Job with the same `check_in` that the pod uses, so one write clears the check-out, records the end and releases the claim.
- **The pod judges, the Service decides.** The pod failure policy runs the pod again only for exit 75. Every later attempt is a new create of the row, after the failure wait of the class (`RETRY_AFTER`). The row deletes an ended Job of the same name only when it creates the Job again, so a failed Job stays for diagnosis while its item waits.
- **The name is the item and the body.** The input key of `RepoRef.unit_name` is the hash of the body without the block of the alternatives job (`plan_body_hash`). A second create for the same body gets 409, and an edit of the body gives a new Job.
- **A plan that keeps failing is divided.** The counted ends share the count of the refused plans on one body (`stage.plan_defects`, `roadmap.stage.plan_defect_limit`). At the limit the item returns to New with a comment that asks refine to split it, so a large item is not tried again with the same body (owner rule 2, 2026-11-13).
- **Free evictions.** A drain or a delete of a Job is no fault of the item. The first 3 on one body are free and the item is due at once, and the row judges the orphan of the freed item at any age, so the item gets its Job in the same round.
- **Orphans before creates.** The selection of the row reads the heads without the branch of each orphan that the writer removes, so the item of an old orphan gets its Job in the same round. The Job removes its own orphan at once if the removal of the row failed.
- **Timeouts nest.** Tool and request timeouts < model call < `roadmap.stage.time_budget_seconds` (9000) < `activeDeadlineSeconds` (10800) <= the admission cap (14400). The row deletes a running Job only 600 s after the deadline of its check-out, so the Job controller ends the Job and the pod checks in first.

## Rejected alternatives

- **A Lease as the lock.** The Job list and the 409 of the name hold one Job for each item and body with no new object. A Lease arrives with the engine item.
- **A ledger file for the stage Jobs.** The record of the item holds the check-out and the failure marks that the selection already reads, so a second ledger would repeat the failure wait.
- **Delete each ended Job at once.** The log of a failed Job is the evidence of its class. The TTL of the template (1 day) removes it, or the next create of the item does.
- **A reserve of the stage Jobs in the GitHub budget of the Service.** Each Job counts in a budget of its own until the shared budget (#4563, #5497).
