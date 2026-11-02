# Design

## Decisions

- **The watch reads check runs only, through `read_check_runs`, and the App token keeps no `statuses` permission.**: The repository sets no commit status, so the status call has no use, and adding a permission is a person's decision.
- **`assess_merge_readiness` takes a `checks` reader that defaults to `read_commit_checks`, and `monitor_pr` passes it through.**: `devops pr check-readiness` and `devops pr monitor` run with a person's token, which may read commit statuses, so their behavior stays as it is.
- **`watch_pull` passes `read_check_runs` to `monitor_pr`.**: The implement job is the only caller that acts as the App, so only its read changes.

## Rejected alternatives

- **Add the `statuses` read permission to the App token.**: `docs/adr/0015-roadmap-jobs-act-as-a-github-app-on-the-personal-account.md` says a permission change is the owner's decision, and the repository sets no commit status, so the grant would be unused.
- **Make `_judge_checks` call `read_check_runs` for every caller.**: `src/devops_cli/github/merge_readiness.py:239` serves `devops pr check-readiness` and `devops pr monitor` too, and `tests/github/test_merge_readiness.py` covers commit statuses there, so a global change would drop a read those callers use.
- **Copy the check read into `implement_pull.py`.**: `read_check_runs` in `src/devops_cli/github/check_verdict.py` already reads check runs only, so a copy would duplicate it.
