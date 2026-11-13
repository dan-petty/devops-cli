# Design

## Decisions

- **Read the pull request's file list from the compare endpoint of the base commit and the head commit.**: That compare is the diff the squash merge applies, and it follows the merge base when a merge commit moves it.
- **Name a fork's head as the head owner and branch, and any other head by its commit sha.**: A fork's head commit is no commit of the base repository, so the compare of the base cannot resolve it there.
- **Report a compare answer of 300 files as a possibly truncated list, as one grounding blocker that names the limit.**: A change folder beyond the cap would give the same false blocker this issue reports, and the project already holds a compare answer at the limit with a blocker naming the failure.
- **Keep the merge-base read on its own model and give the file read `_CompareFiles`.**: `get_merge_base` reads the same endpoint for one field, and a malformed file entry must not break the review runner's merge-base read.
- **Carry the truncation as a field of `ChangedFilesRead` and not as its error text.**: A truncated list was read and is incomplete, so it gets its own text and not the text of a failed read.
- **Read `read_draft`'s file list from the compare endpoint too, by the base sha that `PullStatus` now carries.**: The readiness run calls `read_draft` for an implement pull request, so a pulls files read there would still end a request path of the run with the pulls files path.
- **Keep `GitHubClient.get_pull_files` for the review runner and `devops ai analyze pr`, and change only the readiness reads.**: `search_code` for `get_pull_files` lists those reads outside the readiness run, and the definition stays for them.
- **Read the state into `PRMonitorStatus` and return before the verdict for a pull request that is not open.**: A merged or closed pull request cannot become ready, so no check read and no review read can change the result.
- **Print the monitor's result message and exit with its code for a terminal state, before the summary and the ready line.**: The monitor already builds the merged and closed messages and their exit codes, and the command discarded both on exit 0.
- **Exit 2 for a closed unmerged pull request.**: It is neither ready, nor a check failure, nor a timeout, and 2 is the monitor's code for another blocker.
- **Skip the check-count line of the status callback for a terminal state.**: The callback printed `Checks: 0/0 passed` for a pull request whose checks were never read.
- **Change the living requirement that holds the monitor's exit codes with the merged and closed cases.**: An unmodified requirement would keep saying that a pull request with no blocker exits 0, which contradicts exit 2 for a closed unmerged pull request.
- **Give the monitor's poll stop and closed result the test file that its module docstring names for the loop and exit codes.**: `tests/github/test_github_pr_monitor.py:4:The monitor judges the rest through the merge-readiness verdict; its loop and exit codes are` says that loop and those codes are tested in `tests/commands/test_pr.py`.
- **Split the monitor module's state read and the command's output into two groups, and give the command's group both command test files.**: Each module keeps its own existing test file, and the module's group runs `tests/commands/test_pr.py` for the loop and the exit codes it changes.

## Rejected alternatives

- **Keep the pulls files endpoint and refresh the base before judging.**: The issue records 184 files from that endpoint against 11 from the compare and 11 in the squash commit, and `src/devops_cli/github/merge_readiness.py:359:return ChangedFilesRead(client.get_pull_files(f"{owner}/{repo_name}", pr_num))` is the read that asks for it.
- **Leave `read_draft` on the pulls files endpoint because it reads only an implement pull request.**: `src/devops_cli/roadmap/implement/implement_pull.py:276:files = client.get_pull_files(repo, number)` runs inside `devops pr check-readiness`, so a request path of the run would still end with the pulls files path.
- **Fall back to the pulls files endpoint when the compare answer holds 300 files.**: That is the endpoint whose stale base caused the false not-grounded blocker of the issue.
- **Judge grounding on the 300 files of a truncated compare answer.**: A change folder beyond the cap would give the same false blocker that the issue reports.
- **Read and name the checks that still run after a pull request merges.**: `src/devops_cli/github/pr_monitor.py:539:if status.merged:` returns before any check read, and a check that runs after the merge cannot change the result.
- **Keep the READY line and add a merged note beside it.**: `src/devops_cli/commands/pr.py:610:f"**State**: {'Ready for Merging' if result.success else 'Action Required'}"` and the ready line at `src/devops_cli/commands/pr.py:804:print_success(MESSAGES.pr.pr_ready_success.format(number=pr_number))` would still call a merged pull request ready for merging.
- **Exit 0 for a closed unmerged pull request.**: The command would report a pull request that can no longer merge as a success.
- **Keep the pulls files request in the dry-run plan of check-readiness.**: The plan would name a request that the command no longer makes, as `src/devops_cli/github/pr_plans.py:368:target=f"repos/{target_repo}/pulls/{num_str}/files"` does today.
- **Rely on `tests/github/test_github_pr_monitor.py` alone for the closed result and the poll stop.**: That file's own rule at `tests/github/test_github_pr_monitor.py:4:The monitor judges the rest through the merge-readiness verdict; its loop and exit codes are` puts the loop and the exit codes in `tests/commands/test_pr.py`.
