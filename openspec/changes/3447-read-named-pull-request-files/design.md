# Design

## Decisions

- **Add `pull_requests` to `VerificationInput` in `src/devops_cli/roadmap/stage/stage_verify.py`.**: The pass reads one JSON document, and the payload already separates the issue, the plan and the files. A separate key keeps a repository file apart from a pull request file, so a path stays exact and the model can tell them apart.
- **Read the pull request with `GitHubClient.get_pull` and read its files with the `git` wrapper of `src/devops_cli/roadmap/clone_git.py`.**: One REST read gives the merge commit, and the fetch follows the rule of the stage job that it plans on the commit that it fetched from origin. The local read reuses the bounded, read-only git read.
- **Match only the phrase `pull request #` or `PR #`, in any case.**: The #3410 body holds `pull request #3378` and the bare references `#3410` and `#3435`, so the phrase reads the pull request and no unrelated issue number.
- **Give no entry for a pull request that is not merged, or that cannot be read.**: The pass must go on, and the read must never stop the plan. `pull_request_files` catches the failure of the REST read and of the git read and returns no entry.
- **Bound the read with `CONST_ROADMAP_STAGE_VERIFY_MAX_FILES` and `CONST_ROADMAP_STAGE_VERIFY_FILE_MAX_TOKENS`, the OpenSpec change folder first.**: The two constants already bound a cited file. The change folder holds the plan of the pull request, which is the file that most often contradicts a claim.
- **Cache the read by number on the planner.**: A repair round makes a later review, which builds a new input. One read for each pull request for the item keeps the cost down.
- **Add `merged` and `merge_commit_sha` to `PullRequest` in `src/devops_cli/github/client.py`.**: The REST read of a pull request returns both. GitHub also gives a test merge commit for an unmerged pull request, so the read checks `merged` and not `merge_commit_sha` alone.

## Rejected alternatives

- **Merge the pull request files into `files` with a path prefix.**: A path can collide with a repository path, and the model cannot tell a repository file from a pull request file.
- **Send only the paths that the claim names.**: A plan file that the claim does not cite can contradict the claim.
- **Read the GitHub changed-files and contents endpoints for each file.**: It needs one request for each kept file, each paced and charged on the identity's quota ledger, and the contents answer is cut and encoded.
- **Read the local merge ref `refs/pull/<number>/merge`.**: The ref can be absent, and it does not name the merge commit for every merge method.
- **Return the item when its body states a false premise.**: #3478 removed `premise_failed` from `StageProposal` (`src/devops_cli/roadmap/stage/stage_change.py:685`). A body-claim return needs a reply field and a return path that the deferred item #5701 adds. This change reports the finding and returns the plan to the planner.
- **Let the model choose the pull request numbers.**: The input is built before the model call and must be testable.
