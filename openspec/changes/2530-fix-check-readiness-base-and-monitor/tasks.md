# Tasks

## 1. Read the compare answer's files in the GitHub client

Kind: behavior. Reads: `src/devops_cli/github/client.py`, `tests/github/test_github_client.py`, `tests/support/fakes/github.py`. Changes: `src/devops_cli/github/client.py`, `tests/github/test_github_client.py`.

- [x] 1.1 `tests/github/test_github_client.py::test_the_compare_files_are_read_with_the_limit_flag` fails: it scripts a compare answer of two commits with two files and asserts those files and a false truncation flag, then an answer of 300 files and asserts a true flag, and the client has no such read
  - Verification: `$ uv run devops ci test tests/github/test_github_client.py` fails on the base
- [x] 1.2 Add `_CompareFiles`, the named tuple `CompareFiles` with `files` and `truncated`, the constant `_COMPARE_FILES_LIMIT = 300` and the method `get_compare_files` to `src/devops_cli/github/client.py`. The method sends one GET to `compare/{base}...{head}?per_page=1`, reads the `files` of the answer, and sets `truncated` when the answer holds `_COMPARE_FILES_LIMIT` files. Leave `get_merge_base` and `_Comparison` as they are
  - Verification: `$ uv run devops ci test tests/github/test_github_client.py` passes

## 2. Readiness reads the compare and reports the file limit

Kind: behavior. Reads: `src/devops_cli/github/client.py`, `src/devops_cli/github/merge_readiness.py`, `src/devops_cli/roadmap/grounding.py`, `src/devops_cli/lang/en/messages.py`, `tests/github/test_merge_readiness.py`, `tests/support/fakes/github.py`, `tests/commands/test_pr.py`. Changes: `src/devops_cli/github/merge_readiness.py`, `src/devops_cli/roadmap/grounding.py`, `src/devops_cli/lang/en/messages.py`, `tests/github/test_merge_readiness.py`, `tests/support/fakes/github.py`, `tests/commands/test_pr.py`.

- [x] 2.1 `tests/github/test_merge_readiness.py::test_the_changed_files_are_read_from_the_compare_of_the_base_and_head` fails: it scripts the compare answer with the archived change folder and asserts a ready verdict, and the read still asks the pulls files endpoint
  - Verification: `$ uv run devops ci test tests/github/test_merge_readiness.py tests/commands/test_pr.py` fails on the base
- [x] 2.2 Give `read_changed_files` the pull request payload and read the files with `GitHubClient.get_compare_files`. The base is the base sha of the payload. Add `_compare_head`: the head owner, a colon and the head ref when the head repository is not the base repository, and the head sha otherwise. Add `truncated: bool = False` to `ChangedFilesRead` in `src/devops_cli/roadmap/grounding.py` and pass it. In `_judge_grounding`, block once with a message naming GitHub's limit of 300 files when the list is truncated, and return before `plan_blockers` and `grounding_blockers`. Add the message to `MESSAGES.pr` in `src/devops_cli/lang/en/messages.py`. Add `route_compare_files` beside `route_merge_base` in `tests/support/fakes/github.py`, answering `merge_base_commit` and `files`. Update the one production call and the two test calls of `read_changed_files`, the file routes of `tests/github/test_merge_readiness.py`, and the readiness rows of `tests/commands/test_pr.py`
  - Verification: `$ uv run devops ci test tests/github/test_merge_readiness.py tests/commands/test_pr.py` passes

## 3. Read an implement draft's files from the compare

Kind: behavior. Reads: `src/devops_cli/github/client.py`, `src/devops_cli/roadmap/implement/implement_pull.py`, `tests/roadmap/test_roadmap_draft_readiness.py`. Changes: `src/devops_cli/github/client.py`, `src/devops_cli/roadmap/implement/implement_pull.py`, `tests/roadmap/test_roadmap_draft_readiness.py`.

- [x] 3.1 `tests/roadmap/test_roadmap_draft_readiness.py::test_read_draft_reads_the_files_from_the_compare_of_the_base_and_head` fails: it gives a pull status with a base sha and a head sha, asserts that `get_compare_files` is called with them and that `get_pull_files` is not, and `read_draft` still asks the pulls files endpoint
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_draft_readiness.py` fails on the base
- [x] 3.2 Add `base_sha` to `PullStatus` in `src/devops_cli/github/client.py`, read from the base sha of the payload. In `read_draft` of `src/devops_cli/roadmap/implement/implement_pull.py`, replace the pulls files read with `client.get_compare_files(repo, pull.base_sha, pull.head_sha).files`. Update the `read_draft` tests of `tests/roadmap/test_roadmap_draft_readiness.py` that stub the pulls files read, so they stub `get_compare_files` with `CompareFiles`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_draft_readiness.py` passes

## 4. Read the pull request state on every monitor poll

Kind: behavior. Reads: `src/devops_cli/github/pr_monitor.py`, `tests/github/test_github_pr_monitor.py`, `tests/commands/test_pr.py`. Changes: `src/devops_cli/github/pr_monitor.py`, `tests/github/test_github_pr_monitor.py`, `tests/commands/test_pr.py`.

- [ ] 4.1 `tests/commands/test_pr.py::test_a_closed_pull_request_stops_the_monitor_with_exit_2` fails: it scripts a closed pull request payload, asserts one poll read and exit 2, and the monitor judges the closed pull request as ready
  - Verification: `$ uv run devops ci test tests/github/test_github_pr_monitor.py tests/commands/test_pr.py` fails on the base
- [ ] 4.2 Add `state` to `PRMonitorStatus` and set it from the state of the payload in `get_pr_monitoring_status` of `src/devops_cli/github/pr_monitor.py`. Return the status before `assess_merge_readiness` when the state is `closed`. Stop the poll of `monitor_pr` on a status that is merged or closed at `src/devops_cli/github/pr_monitor.py:655:if latest_status.merged or (`. In `_settled_result`, return the closed result with exit code 2 and the message `PR #<number> is closed.` after the merged result
  - Verification: `$ uv run devops ci test tests/github/test_github_pr_monitor.py tests/commands/test_pr.py` passes

## 5. Print a terminal monitor result with no check count

Kind: behavior. Reads: `src/devops_cli/commands/pr.py`, `src/devops_cli/github/pr_monitor.py`, `tests/commands/test_pr_cmd.py`, `tests/commands/test_pr.py`. Changes: `src/devops_cli/commands/pr.py`, `tests/commands/test_pr_cmd.py`, `tests/commands/test_pr.py`.

- [ ] 5.1 `tests/commands/test_pr_cmd.py::test_a_merged_pull_request_prints_merged_with_no_check_count` fails: it answers a merged pull request payload and asserts the merged line, no checks line and exit 0, and the command prints the ready line
  - Verification: `$ uv run devops ci test tests/commands/test_pr_cmd.py tests/commands/test_pr.py` fails on the base
- [ ] 5.2 In `monitor_pr_command` of `src/devops_cli/commands/pr.py`, print `result.message` and raise `typer.Exit(result.exit_code)` when the status is merged or closed, before `_render_monitor_summary` and the ready line at `src/devops_cli/commands/pr.py:804:print_success(MESSAGES.pr.pr_ready_success.format(number=pr_number))`. Skip the check-count line of `_status_cb` for a status that is merged or closed. Name a merged pull request and a closed pull request in the state line of `_format_markdown_monitor_summary`. Add the merged and the closed output cases to `tests/commands/test_pr_cmd.py` beside `test_pr_monitor_no_open_pr`, and update the markdown row of `tests/commands/test_pr.py`
  - Verification: `$ uv run devops ci test tests/commands/test_pr_cmd.py tests/commands/test_pr.py` passes

## 6. Plan the compare request in the check-readiness dry run

Kind: behavior. Reads: `src/devops_cli/github/pr_plans.py`, `src/devops_cli/commands/pr.py`, `tests/commands/test_pr_dry_run.py`. Changes: `src/devops_cli/github/pr_plans.py`, `tests/commands/test_pr_dry_run.py`.

- [ ] 6.1 `tests/commands/test_pr_dry_run.py::test_the_check_readiness_plan_lists_the_compare_request` fails: it asserts that the plan holds a compare target and no pulls files target, and `plan_pr_check_readiness` still lists the pulls files target
  - Verification: `$ uv run devops ci test tests/commands/test_pr_dry_run.py` fails on the base
- [ ] 6.2 Replace the pulls files request of `plan_pr_check_readiness` in `src/devops_cli/github/pr_plans.py` with one GET whose target is `repos/{target_repo}/compare/<base>...<head>` and whose argv reads that path with `?per_page=1`
  - Verification: `$ uv run devops ci test tests/commands/test_pr_dry_run.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
