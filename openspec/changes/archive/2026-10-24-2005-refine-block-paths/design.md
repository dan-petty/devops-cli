# Design

## Context

`_still_waiting` in `src/devops_cli/roadmap/refine.py` decides whether an unchanged item still waits on its next step (#1758). It reads the comments on the item and ends the wait when a comment follows refine's last one, or when each recorded blocker is closed. The job record holds the step and the blockers (`RefineRecordKey`). See proposal.md for the motivation.

## Goals / Non-Goals

**Goals:**

- Refine records the paths that its proposal cites as the cause of a block.
- A round looks at a waiting item again when a commit on the default branch changed one of those paths at or after refine's last comment, and makes no model call for an item whose paths did not change.

**Non-Goals:**

- A change to a function that the block names, but not to a file. The proposal gives the file that holds the function.
- Commits that land on the default branch between the checkout that refine reads and its comment. Refine reads `--source` at the start of a round, and the Service's clone is current at that time.

## Decisions

- **The model names the paths in a field of its proposal (`block_paths`).** The proposal knows the code from its `context`, which holds the files and lines that the issue cites. Refine keeps only the paths that the checkout holds at the refined commit, as it does for the sources of a fact, so a path the model invents is not recorded.
  - Rejected: take the paths from the text of `suspected_block` with `_CITED_PATH_RE`. The prompt asks for one line about what the work waits on, and a block that names a function has no path in that line.
- **The time of refine's last comment comes from the comments listing.** `_still_waiting` already reads that listing for each waiting item, and GitHub gives `created_at` for each comment. The commit time comes from GitHub too, so no local clock is compared with GitHub's.
  - Rejected: record the time of the round in the job record. That compares the clock of the host that runs refine with GitHub's commit times, and it adds a record key for a time that the comment already holds.
- **One commit read for each path, from the commits listing (`commits?path=<path>&per_page=1`).** The listing gives the newest commit first, so its first entry is the last change of the path. The GitHub store keeps the time of each path for its life, one round, so two waiting items that cite one path cost one read. A path that a commit deleted still has that commit, so a deletion also ends the wait.
  - Rejected: `commits?path=<path>&since=<comment time>` for each item. It needs one read for each item and path, and the time differs for each item.
  - Rejected: the compare API from the commit that refine read. The checkout's HEAD can be a commit that GitHub does not have, and then the compare fails.
  - Rejected: `git log -- <path>` in the `--source` checkout. It gives the state of a local checkout, which can be behind the default branch or on another branch.
- **"At or after" the comment.** GitHub gives both times to the second. A commit in the second of the comment was possibly not in the code that refine read, so it ends the wait. One extra model call costs less than an item that waits on a cause that is gone.
- **Paths only for a block.** Refine records the paths when the item has an open dependency or a suspected block. A proposal with open questions or a split and no block records none, so a change to code does not end a wait for a person's answer.
- **At most five paths.** `CONST_ROADMAP_REFINE_MAX_BLOCK_PATHS` bounds the reads for each waiting item. The paths go into the job record as a comma-separated list; `_CITED_PATH_RE` accepts no comma in a path.

## Risks / Trade-offs

- [More REST requests in each round] → only an item that still waits after the comment check reads its paths, at most five, and a path is read one time in a round. The dry-run plan lists the read.
- [The model gives no path for a block that code causes] → the item waits as before #2005, on a reply, a body edit or its blockers.
