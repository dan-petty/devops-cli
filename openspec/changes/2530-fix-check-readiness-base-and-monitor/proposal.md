# Proposal

## Why

The issue #2530 reports two wrong states of the `devops pr` commands. `devops pr check-readiness` judged a stale file list from the pulls files endpoint, which keeps the base of the last push, so a merge commit that moved the merge base gave a false not-grounded blocker naming archived changes of other issues. `devops pr monitor` read `merged` but printed `Checks: 0/0 passed` and the ready line on every exit 0, so a pull request merged while it waited was reported 100% ready, and a closed unmerged pull request had no terminal result at all.

## What Changes

- `devops pr check-readiness` reads the files a pull request changes from the compare endpoint of the base commit and the head commit, and no request of the run asks for the pulls files path.
- `GitHubClient.get_compare_files` returns the compare answer's files with a flag that says the answer holds GitHub's limit of 300 files.
- `read_changed_files` names the compare head as the head owner and branch when the head repository is not the base repository, and as the head commit sha otherwise.
- A compare answer at the 300-file limit is one grounding blocker that names the limit, and the rules that read the file list do not run on that partial list.
- `read_draft` reads an implement pull request's files from the compare endpoint, so the readiness run makes no pulls files request.
- `devops pr monitor` reads the pull request state on every poll and stops polling a pull request that is merged or closed.
- A merged pull request prints `PR #<number> is merged.` and exits 0, with no checks line and no ready line.
- A closed unmerged pull request prints `PR #<number> is closed.` and exits 2, with no checks line and no ready line.
- The markdown summary names a merged pull request as merged and calls no merged pull request ready.
- The dry-run plan of `devops pr check-readiness` lists the compare request and no pulls files request.
- The living requirement that holds the monitor's exit codes names the merged and closed cases, so the exit code 2 of a closed unmerged pull request does not contradict the 0 of a pull request with no blocker.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pr-merge-readiness`: Readiness reads the file list at the merge base, The compare head of a fork is named by owner and branch, A compare answer at the file limit is reported, The monitor reads the pull request state on every poll, The monitor reports a terminal pull request with no check count, The markdown names a merged pull request as merged, The check-readiness plan lists the compare request, The monitor waits until the checks settle and names every blocker

## Impact

- Code: `src/devops_cli/github/client.py`, `src/devops_cli/github/merge_readiness.py`, `src/devops_cli/roadmap/grounding.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/implement/implement_pull.py`, `src/devops_cli/github/pr_monitor.py`, `src/devops_cli/commands/pr.py`, `src/devops_cli/github/pr_plans.py`
- Tests: `tests/github/test_github_client.py`, `tests/github/test_merge_readiness.py`, `tests/support/fakes/github.py`, `tests/commands/test_pr.py`, `tests/roadmap/test_roadmap_draft_readiness.py`, `tests/github/test_github_pr_monitor.py`, `tests/commands/test_pr_cmd.py`, `tests/commands/test_pr_dry_run.py`

## Feasibility

- `probes` holds this line, word for word: The path `src/devops_cli/github/merge_readiness.py` is a file of the staging commit. That file holds the readiness read, so the premise of the issue is checked against the staged tree.
- `probes` holds this line, word for word: The path `src/devops_cli/github/client.py` is a file of the staging commit. That file holds the GitHub reads the change extends.
- `probes` holds this line, word for word: The path `docs/adr/0006-github-session-requests-go-through-gidgethub.md` is a file of the staging commit. That ADR is the decision that the session's requests go through gidgethub.
- `probes` holds this line, word for word: The path `CHANGELOG.md` is a file of the staging commit. It holds the recorded compare limit that the plan names.
- `read_file` of `src/devops_cli/github/merge_readiness.py` lines 353 to 361 showed `src/devops_cli/github/merge_readiness.py:359:return ChangedFilesRead(client.get_pull_files(f"{owner}/{repo_name}", pr_num))`.
- `callers` for `read_changed_files` answered one production call at `src/devops_cli/github/merge_readiness.py:589:changed = read_changed_files(owner, repo_name, pr_num, session=session)` and two calls in `tests/github/test_merge_readiness.py`, so the payload reaches the read through one call.
- `search_code` for `_judge_grounding` answered `src/devops_cli/github/merge_readiness.py:466:def _judge_grounding(` and the grounding rules of that function read the file list at `src/devops_cli/github/merge_readiness.py:524:for text in grounding_blockers(grounding):`.
- `read_file` of `src/devops_cli/github/client.py` lines 440 to 489 showed the pulls files read at `src/devops_cli/github/client.py:445:def get_pull_files(self, repo: str, number: int) -> list[PullRequestFile]:` and the compare read at `src/devops_cli/github/client.py:484:endpoint = _repo_path(repo, f"compare/{quote(base)}...{quote(head)}?per_page=1")`.
- `file_symbols` for `src/devops_cli/github/client.py` lists `477: def get_merge_base(self, repo: str, base: str, head: str) -> str | None:`. `probes` says that `GitHubClient` defines no field `get_merge_base`, which is true of a field and not of this method.
- `read_file` of `src/devops_cli/roadmap/implement/implement_pull.py` lines 255 to 292 showed the pulls files read of `read_draft` at `src/devops_cli/roadmap/implement/implement_pull.py:276:files = client.get_pull_files(repo, number)`, and the pull it holds gives `head_sha` and no base sha.
- `read_file` of `src/devops_cli/github/pr_monitor.py` lines 520 to 593 showed the merged read and the merged result at `src/devops_cli/github/pr_monitor.py:539:if status.merged:` and `src/devops_cli/github/pr_monitor.py:575:message=f"PR #{pr_number} is merged.", status=status`.
- `read_file` of `src/devops_cli/github/pr_monitor.py` lines 617 to 664 showed the poll stop at `src/devops_cli/github/pr_monitor.py:655:if latest_status.merged or (`; the closed state has no stop and no result.
- `read_file` of `src/devops_cli/commands/pr.py` lines 770 to 807 showed the ready line on exit 0 at `src/devops_cli/commands/pr.py:804:print_success(MESSAGES.pr.pr_ready_success.format(number=pr_number))` and the check count at `src/devops_cli/commands/pr.py:782:f"[{elapsed}s] Checks: {st.successful_checks}/{st.total_checks} passed "`.
- `read_file` of `src/devops_cli/commands/pr.py` lines 605 to 623 showed the markdown state line at `src/devops_cli/commands/pr.py:610:f"**State**: {'Ready for Merging' if result.success else 'Action Required'}"`, which calls a merged result ready.
- `file_symbols` for `src/devops_cli/github/pr_plans.py` lists `341: def plan_pr_check_readiness(`, and `read_file` of lines 341 to 380 showed the pulls files request at `src/devops_cli/github/pr_plans.py:368:target=f"repos/{target_repo}/pulls/{num_str}/files"`.
- `search_code` for `limit of 300` answered `CHANGELOG.md:3237` with `whose compare lists GitHub's limit of 300 files`, and no file under `src/devops_cli/config/`; `search_code` for `COMPARE_FILES` answered no match. The plan adds `_COMPARE_FILES_LIMIT` with the value 300.
- `read_file` of `src/devops_cli/roadmap/grounding.py` lines 20 to 41 showed the read result at `src/devops_cli/roadmap/grounding.py:36:class ChangedFilesRead(NamedTuple):` with `error: str = ""` as its last field.
- `read_spec` for `pr-merge-readiness` gave its purpose and its 11 requirement names. The one that holds the monitor's exit codes with no blocker goes into `modified`, so the closed result of 2 does not contradict it.
- `read_file` of `tests/github/test_github_pr_monitor.py` lines 1 to 30 showed its own rule at `tests/github/test_github_pr_monitor.py:4:The monitor judges the rest through the merge-readiness verdict; its loop and exit codes are`, so group 4 changes and runs `tests/commands/test_pr.py` beside that file.
- `read_file` of `tests/commands/test_pr.py` lines 690 to 727 showed the monitor exit-code rows at `tests/commands/test_pr.py:726:exit_code, output = _monitor(cli, "--timeout", "120")`, so a closed row fits that table.
- `list_files` of `tests/commands` listed `test_pr.py`, `test_pr_cmd.py` and `test_pr_dry_run.py`, and `search_code` for `def test_pr_monitor` answered `tests/commands/test_pr.py:718:def test_pr_monitor_exits_on_the_verdict_once_the_checks_settle(`.
- `read_file` of `tests/github/test_merge_readiness.py` lines 25 to 50 showed the pulls files route at `tests/github/test_merge_readiness.py:38:_FILES = f"/repos/{_REPO}/pulls/{_PR}/files?per_page=100"`.
- `read_file` of `tests/support/fakes/github.py` lines 190 to 208 showed the compare route helper at `tests/support/fakes/github.py:202:def route_merge_base(api: GitHubApiFake, repo: str, base: str, head: str, sha: str) -> None:`, which the new file route sits beside.
- `read_issue` for #2509 answered that the pull request merged, and `find_issues` for `check-readiness` listed no open item that changes the readiness file list; #4927 changes a monitor poll that reads no check.
- `GitHubClient.get_compare_files` needs a client of the GitHub API and a network: it sends one GET through the session, which paces, charges and retries it.
- `read_changed_files` needs a client of the GitHub API and a network: it reads the compare through `get_github_session()` when the caller gives no session.
- `read_draft` needs a client of the GitHub API and a network: it reads the compare through `get_github_session()` when the caller gives no client.
- `fetch_pr_details` needs a network: the monitor reads the pull request payload on every poll.
- `monitor_pr` needs a network: each poll reads the pull request, its checks, its review threads and its reviews.
- The plan introduces no command and no verify program. Every `verify` runs `uv run devops ci test` over existing test files, `uv` and `devops` are in the runner image, and a failing test is the `test` failure class that the job repairs.
- The 300-file cap of the compare answer is not checked against GitHub in this run: `CHANGELOG.md:3237` records it. A fork head is not checked either, so that case rests on the `head.repository` field of the payload: not checked.
- The first checks of the implementation are `uv run devops ci test tests/github/test_github_client.py`, then `uv run devops ci test tests/github/test_merge_readiness.py`, then `uv run devops ci test tests/roadmap/test_roadmap_draft_readiness.py`.

## Existing Tool Considered

gidgethub 6.0.0 (Apache-2.0, last activity 2026-09-25, maintained) is the GitHub REST client that ADR 0006 chooses, and the session already reaches the compare endpoint through it. The change adds no dependency and no second client: it reads the compare answer's `files` through the same session, and it changes what the two commands print for a terminal pull request.

## Dependencies

None.
