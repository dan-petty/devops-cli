# Proposal

## Why

Issue #3646. A rebase that stops on a conflict stops the item with the class `conflict`, but the stop comment does not name the conflicted files. `_sync` in `src/devops_cli/roadmap/implement_run.py` builds the reason from the error text, then aborts the rebase. After the abort, git keeps no record of the conflict. The error text comes from `git_message`, which reads only stderr, and git writes `CONFLICT (content): Merge conflict in <file>` to stdout. A person or a repair step must find the files again.

## What Changes

- `_sync` reads the unmerged files with `git diff --name-only --diff-filter=U -z` before `git rebase --abort`. Each path is masked and escaped. The list is cut to `CONST_ROADMAP_IMPLEMENT_REASON_PATHS` paths, and the text says how many paths the cut left out.
- The reason of the stop names the files. `_StopError` carries them, and the stop passes the class `conflict` itself, so a file name cannot change the class.
- The job record has a new key, `implement.conflict`, that holds the listed files as JSON. A stop sets it, and a retry clears it with the other marks of the stop.
- The change alters what the stop comment and the job record hold, which a consumer observes. So it carries a spec delta.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job`: a conflict stop names its files.

## Impact

- Code: `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/roadmap/store.py`, `src/devops_cli/lang/en/messages.py`.
- Tests: `tests/roadmap/test_roadmap_implement_job.py`.

## Acceptance

- A real git repository with a conflict at the start of a run stops the item with class `conflict`, and the comment names each conflicted file.
- The same holds for the rebase before the push.
- The job record holds the files after the stop, and holds none after a retry.
- A list of files above the limit is cut, and the comment states how many files the cut left out.
- A path that holds a secret is masked in the comment and in the record.

## Feasibility

Checked on 2026-11-07 at `origin/main` (163a5c21).

- A test repository with a real rebase conflict, run through the same `git` function, gave the stop text without a file name, as the issue says. `git diff --name-only --diff-filter=U` lists the unmerged files while the rebase is in progress, and lists none after `git rebase --abort`.
- The read needs no tool beyond git.

## Existing Tool Considered

`git diff --name-only --diff-filter=U` gives the list, and the change adds no tool. The change reuses `CONST_ROADMAP_IMPLEMENT_REASON_PATHS` (20 paths) and the text `implement_paths_more`, which the other stops use to cut a list of paths, so it adds no constant. It deletes no code. The cost to build is about 40,000 tokens, with little to keep.
