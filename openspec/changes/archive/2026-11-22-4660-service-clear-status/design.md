# Design

## Decisions
1. **The row `implement` removes the labels.** Each round of the row calls `clear_closed_issues` after its first Status sweep, before the round can wait on a running Job. Reason: the row runs every 7 minutes in its own lane, and the trigger `("webhook", "issues", "closed")` already makes it due (`CONST_ROADMAP_STAGE_BATCH_KEYS`). So one code path serves the event and the poll, and the change adds no schedule and no route.
2. **The router stays as it is.** The `issues.closed` delivery stays a trigger that makes the rows `stage` and `implement` due. The router writes no label (ADR 0021, section 1; `docs/SERVICE_PATTERNS.md` IN3). Reason: a scoped update for `closed` would replace the trigger, and the rows that the close makes due, such as `stage` for its `planned_limit`, would then wait for their interval.
3. **The clear is in `status_sync.py`.** The module holds `write_status`, the one Status writer. The structural test lets only this module and the stores remove a `status/` label.
4. **One request for each label.** `clear_closed_labels` calls `store.unlabel_issue(number, label)` once for each `status/*` and each `owner/*` label. The families come from `family_prefix(ItemField.STATUS)` and `family_prefix(ItemField.OWNER)`, compared in lower case, as `item_of` reads labels. The store removes the label from its kept listing, so a second sweep of the same store, and the next round, send no request.
5. **Read the issue again before the removal.** The listing of a round can be older than a reopen. `clear_closed_labels` reads the issue, and keeps the labels of an issue that is open or gone. The workflow also read the labels when it ran, not the labels of the event. The read costs one request only for a closed issue that still holds a managed label.
6. **Every issue, not only Items.** `clear_closed_issues` reads `store.issues()`, so a closed Candidate with `status/new` also loses the label, as the workflow did. It turns each issue into an Item with `item_of` for `write_each`, so a failed issue does not stop the others, and a rate limit stops the clear.
7. **The failures join the Status failures of the round.** The round adds the failures of the clear to `status_failed`, so the row fails as for a failed Status write (`raise_for_failed`).
8. **Onboard checks six prerequisites.** Row 5 and its constants are deleted. The `service.repos` row becomes row 5 and the webhook row becomes row 6, so the numbers have no gap. `onboard_requests` reads no workflow file.
9. **ADR 0016 gets a Status History line.** The line names the owner decision in #4627 and the Service as the remover. The body of the accepted record does not change.

## Rejected alternatives
- **The clear in `sync_statuses`, as the refine plan said.** Rejected: the rows `stage` and `implement` both call `sync_statuses` in their own lanes, and the close makes both due at once. Two lanes can then remove the same label, and GitHub answers 404 to the second `DELETE`. `raise_for_failed` then fails the row. One row gives one writer.
- **A scoped update for `issues.closed`.** Rejected: `roadmap_consumer` runs a scoped update in place of the trigger, so the close no longer makes the rows `stage` and `implement` due in the same lane, and the wake after a scoped update leaves out the lane that ran it.
- **The router removes the labels in the request.** Rejected: ADR 0021, section 1, and IN3 keep the router to the answer, the trigger and the due mark.
- **A reusable workflow, or `actions-ecosystem/action-remove-labels`.** Rejected: each needs a workflow file in each repository, which is the row that this change removes.
- **probot/probot.** Rejected: a second receiver in Node.js beside the Python router, with the handler and the reconcile still written.
- **One `PUT` of the label list without the managed labels.** Rejected: it replaces every label, and it can drop a label that another writer adds between the read and the write.
- **Keep row 5 and leave a gap in the numbers.** Rejected: the spec prints one row for each prerequisite, and the rows would read 1 to 4, 6 and 7.
