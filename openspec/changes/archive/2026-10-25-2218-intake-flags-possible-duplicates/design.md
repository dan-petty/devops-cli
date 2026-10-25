# Design

## A verdict is a flag

The model compares a candidate with its nearest items and can name one that asks for the same change. Intake now places the candidate in every case, and the verdict becomes a field of the decision: `possible_duplicate`, with `duplicate_reason`. The report and the reason comment name the possible original, as they name a related item. A person, or refine, closes one of the two when they ask for the same change.

The cost is now on the safe side. A missed duplicate stays open until a person closes it. A false positive no longer loses a candidate or hides an issue.

Rejected: check the shared change in code and keep the close. The three true duplicates of `tests/fixtures/roadmap/intake-duplicate-judgements.json` have a shared change that is in neither text, so a literal check would reject them.

Rejected: ask the model to quote the sentence of each item that asks for the change, and check each quote against its item. The #1885 false positive passes that check: the umbrella audit holds "one follow-up issue for each tab", and the candidate holds "delete the dashboard Kubernetes and Logs tabs". Both quotes are real, and the verdict is still wrong.

Rejected: keep the close for an existing issue and only stop the drop of a new candidate. A wrong close hides an issue just as a drop loses one, and the earlier rule already held a person's planned issue back for that reason (#1686).

## The retry of a stopped run

A run that filed a new candidate and stopped before the board add leaves an open issue off the board. Before, the next run found it only when the model named it as the original. Now `_new_subject` matches it in code: an open issue that is not finished (off the board, or on it with no Priority) and holds the candidate's title and `filed_body()`. Intake places that issue and files nothing, and the entry point returns its number.

Rejected: match on the title alone. Two candidates can share a title and ask for different changes; the filed body holds the source link and the text, so title and body together name the one filing.

## What goes

Only the duplicate close used the store's `close_as_duplicate` and its GraphQL mutation, the node id read, the duplicate comment and its marker, the held pairs, `IntakeApplied.closed` and the dry-run duplicate steps. The project keeps no compatibility before 1.0, so they go with no shim. The check that skips an issue a person reopened after a duplicate close stays: it reads the timeline, and it respects a person's decision.
