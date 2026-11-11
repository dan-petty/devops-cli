# Design

## Decisions

- **Half-open window on first-parent commits.** A tag becomes its commit through `git log -1 --format=%H%x09%ct <tag>^{commit}`, and its commit time is the time of the window. A time becomes the last first-parent commit of the default branch at or before it (`git log -1 --first-parent --before=@<unix seconds>`). The base commit and the start time are out, and the head commit and the end time are in, so two windows that touch hold each commit and each tag one time.
- **UTC before any compare.** git gives each tag time as `creatordate:unix`, and the resolver makes each option time an aware UTC value. A time with no offset is UTC. No code compares time strings.
- **The default branch is `origin/HEAD`.** `git symbolic-ref refs/remotes/origin/HEAD` names it. A checkout with no origin uses its own `HEAD`.
- **Window ids are safe for a path and a key.** A version window keeps the tag names and replaces each other character with `-`. A week is `YYYY-Www`. A period is `YYYYMMDDTHHMMZ..YYYYMMDDTHHMMZ`. The previous window of a period has the same length and ends at the start. The previous window of a version range ends at the base tag and holds as many releases, in version order.
- **Generated paths come from `.gitattributes`.** `git check-attr --source=<head> linguist-generated` reads the attributes of the head commit, so the split is the same on each run of one window. This is the attribute that GitHub reads to fold a diff. Lock files are in the same list.
- **Net change and churn have a definition each.** The net change is `git diff -M --numstat` from the tree of the base to the tree of the head. The churn is the sum of the numstat of each first-parent commit. Both use numstat, so the review can count the generated paths apart.
- **Hot files follow renames.** The log reads newest first. A rename maps the old path to the newest name of the new path, so an older commit at the old path counts for the same row, and the row names the old path.
- **lizard reads blobs, not a checkout.** For each of the 10 hottest files that lizard can read, the review reads the blob at the base (at its old name when git renamed it in the window) and at the head with `git cat-file blob`, and gives the text to `lizard.analyze_file.analyze_source_code`. A file that a commit does not hold is `null`.
- **The plan and the run share the commands.** Each git command has one builder in `git_read.py`. The run calls it with the values, and the dry run calls it with placeholders, so the plan cannot drift from the run.
- **Each fact carries its provenance.** A fact holds its source, its exact query, its definition and the time of its read. A fact that is not `ok` must give a reason; the model refuses one with no reason.

## Rejected alternatives

- **PyDriller.** It gave 38 commits where `git log --first-parent` gave 37 for the same range, because it does not follow the first parent at the edges of a range.
- **`git archive` of the base and the head.** It writes every file of two trees to read 10 files. `git cat-file blob` reads only the files that lizard measures.
- **`git diff --shortstat` for the net change.** It gives the sums only, so the review cannot count the generated paths apart. The numstat sums are the same: +14,553/-1,600 for `v0.111.0..v0.112.1`.
- **The attributes of the working tree.** A run in another checkout, or after an edit of `.gitattributes`, would give another split for the same window.
- **lizard as a core dependency.** The owner put it in the optional extra `review`; the complexity fact is `skipped` with a reason when it is missing.
