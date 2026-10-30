# Design

## Decisions

- **The closing issue is the link.** The pull request names the issue it delivers with a closing keyword, and GitHub reads that into `closingIssuesReferences`. The commands use that field, so a body that says `Closes #7` and an issue linked by hand both work, and no new parser of text is written.
- **Forward only.** `_REPLACES` lists the Statuses that each target replaces. `devops pr create` after `devops pr ready`, or a second `pr ready`, never moves the Status back. Blocked is never replaced: a person set it, and ADR 0002 says that a job never reverts a person's change.
- **Create and ready, not merge.** The Status of a merged pull request is the close of its issue, and the workflow handles that. No command runs at the merge, because a person merges in the web page.
- **A failure is loud.** The pull request is already open, so the commands exit 1 and say that only the Status is missing. They do not retry in silence. A GraphQL limit makes the read fail with the reason of `gh`; the REST fallback of `pr create` sets no Status, and the later `pr ready` sets In Review.
- **A workflow for the close.** `issues: closed` covers every way to close an issue. The job reads the labels from the event, so it makes no read request, and it removes only labels that start with `status/`.

## Rejected alternatives

- **A new job in the Service for `issues closed`.** It needs a new batch key, a new lane and a round for a one-line write. The webhook may also be off in a checkout that runs without the Service. The workflow runs on GitHub for every repository that holds the file.
- **Parse `Closes #N` from the body.** It misses an issue linked by hand and duplicates what GitHub already computes.
- **A `status/done` label.** ADR 0016 rejected it: the state of the issue already holds Done.
- **Set the Status at merge in `devops pr` commands.** There is no such command. The owner merges in the web page.
