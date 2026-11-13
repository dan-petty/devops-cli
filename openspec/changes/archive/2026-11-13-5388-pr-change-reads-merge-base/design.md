# Design

## Decisions

- **Compare from the base branch name, not from the payload `base.sha`.**: GitHub compares from the merge base of the two commits, so the compare of the base branch and the head commit is the diff that the squash merge applies. The compare from a stale `base.sha` gives the same stale list as the pulls endpoint (#2530: `compare/0137f231...344adba9` gave 184 files, `compare/main...344adba9` gave 11).
- **Name the head by the head commit sha.**: The row reads the checks of that commit, and the pick merges that commit with `--match-head-commit`, so the diff, the checks and the merge are of one commit.
- **Add `GitHubClient.get_compare_diff` beside `get_compare_files`, and give it and `get_pr_diff` one private read of a diff.**: Jev reads a unified diff, and the compare endpoint serves the diff media type that `get_pr_diff` reads. The open change of #5346 adds `get_compare_diff` and `_read_diff` with the same names, signatures, answers and place in the file. The change that merges second gets one conflict in `client.py`, and its resolution keeps one copy of each method. Another place in the file would merge with no conflict and define the method two times.
- **Give `_jev_holds` the `PullStatus` of the draft.**: The status that `_settle` read holds the head commit and `base_ref`, so the check sends no new read of the pull request.
- **Add `client` to the protocol `RestSession` of the pick.**: `GitHubSession.client` gives the typed client of the same session, so the compare request is paced and charged as the other reads of the pick. The tests run the pick on the real session over the GitHub fake.
- **Compare from `ReleasePull.base_ref` and not from the constant `main`.**: A pull request into another base is refused by the branch guard, and the read stays the diff that a merge into its own base applies.
- **Do not add a refusal for a compare answer at GitHub's limit of 300 files.**: The release files are four paths, so a list of 300 files holds at least 296 other paths, and the file guard refuses each.
- **Keep `GitHubClient.get_pr_diff`.**: `devops review pr` reads it on `main` (`src/devops_cli/ai/review/runner.py:952`).

## Rejected alternatives

- **Compare from the payload `base.sha`.**: GitHub does not move `base.sha` when a merge commit moves the merge base, so the compare from it holds the files of the merged base (#2530).
- **Keep the pulls endpoints because GitHub moved `base.sha` in the 16 probed pull requests.**: The probe holds only force-pushes. A merge of the base branch into a plan branch, from `devops pr update-branch` or the update button of GitHub, is the case of #2530, where `base.sha` stayed stale.
- **Build the diff for Jev from the `patch` fields of the compare files answer.**: That writes a diff format by hand, and GitHub serves the unified diff of the same compare in one request.
- **Read the merge base with `get_compare_files` first and then the diff from the merge base.**: That is two requests for one answer. The three-dot compare of the base branch already starts at the merge base.
- **Build item 2 of the issue in this change.**: The compare read of `devops review pr` is only in the open change of #5346. On `main`, the review reads the pulls diff, which holds the files of a merged pull request. A test of item 2 on `main` would pass now and fail when that change merges, so the item moves to #5397.
