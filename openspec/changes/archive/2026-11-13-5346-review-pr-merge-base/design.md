# Design

## Decisions

- **Read the file list from the compare of the base branch name and the head commit sha.**: GitHub compares from the merge base of the two, so this is the diff that the squash merge applies. For pull request 2509, `compare/main...344adba9` gave the 11 files of the squash commit. Readiness reads the same compare (#2530), and the head is a commit sha for a fork too.
- **Read the diff from the compare of the merge base and the head commit.**: The merge base comes from the file read, so the diff and the file list come from one commit, also when the base branch moves between the two requests. The compare of a merge base and its descendant is the diff of the two.
- **Read the base text, the conventions and the base worktree at the merge base of the compare.**: The tip of the base branch can be ahead of the merge base, and symbols added on the base since would read as removed. The fetch of `refs/pull/<n>/head` brings every ancestor of the head, the merge base too, so the local worktree can be made there. The payload's `base.sha` can be absent from the local repository.
- **Return the merge base from `get_compare_files` and delete `get_merge_base`.**: The review needs the files and the merge base of one compare, and one request gives both. The design of #2530 kept the two reads apart so that a malformed file entry did not break the merge base read of the review. The review now needs the files, so that reason is gone.
- **Give the merge base to the review worktrees through `BaseRevision.revision`.**: The branch review gives its base worktree the same field. `_run_pr_review_workflow` then needs no pull request.
- **End `devops review pr` when the compare lists 300 files.**: The compare diff holds every file, but the head files, the symbol deltas and the filter of deleted files read the file list. A review of a partial list would give wrong deltas with no sign. The message names `devops review branch`, which reads the diff with git and has no such limit.
- **Warn and continue in `devops ai analyze pr` when the compare lists 300 files.**: The analysis gives one record for each file, so a partial list gives fewer records and no wrong record. The warning names the limit.
- **List the files of the comment from the base revision of the review.**: The base revision holds the compare that the review read, so the comment names the same files and needs no second request.
- **Delete `get_pull_files`.**: No code in `src/` calls it after this change. Its tests move to the compare read, which parses the same `PullRequestFile` model.

## Rejected alternatives

- **Compare from the payload's `base.sha`.**: For pull request 2509, `compare/0137f231...344adba9` gave merge base 0137f231 and the same 184 files as the pulls files endpoint.
- **Keep the diff of the pulls endpoint and filter it by the compare file list.**: The pulls diff of pull request 2509 held 184 files against 11 in the compare, and a page of a file that both changed would show the changes of `main` too.
- **Read the diff from `compare/<base-ref>...<head-sha>`.**: It is the same diff while the merge base stays, but a push that moves the merge base between the two requests, such as a merge of the head into the base branch, could give a diff from another merge base than the file list.
- **Fall back to the pulls files endpoint when the compare lists 300 files.**: That list keeps the stale base, so the review would read the changes of `main` again.
