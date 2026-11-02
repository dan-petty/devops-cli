# Design

## Decisions

- **A keyword `commit_statuses: bool = True` goes through `monitor_pr`, `get_pr_monitoring_status` and `assess_merge_readiness`. `_judge_checks` reads `read_check_runs` when it is false.**: `read_check_runs` has no `runner` (`check_verdict.py:374-380`) and `read_commit_checks` has one (`:395-402`), so a boolean needs no adapter and no new type, and `_judge_checks` (`merge_readiness.py:239`) is the one place that reads.
- **The default is true, and only `watch_pull` passes false.**: `devops pr monitor`, `devops pr ready` and `devops pr check-readiness` (`commands/pr.py:737`, `:1298`, `:1640`) run with the token of a person, and the scenario `checks-unread` of `tests/commands/test_pr.py:425` keeps its exit 1 for a refused status read.
- **The test runs the whole watch.**: `tests/roadmap/test_roadmap_implement_timeouts.py:150` stubs `monitor_pr`, so a test that stubs it proves only the keyword. `PullFake` in `tests/support/roadmap_implement.py` answers the route `/status`, so a test makes it refuse, and any hop that drops the keyword fails the test with the reason "GitHub could not say whether the checks passed."
- **The failure class of an unread check stays `ci_infra`.**: A read of check runs can still fail for a cause that a retry clears, and `tests/roadmap/test_roadmap_failure.py:179` pins that class.

## Rejected alternatives

- **A `checks` reader argument, a callable.**: The two readers differ by the `runner` argument, so the default `read_commit_checks` needs `functools.partial(..., runner=reads.runner)` and a type for the callable. A call that keeps `runner=` raises `TypeError` for `read_check_runs`. A boolean has one fewer moving part.
- **A field of `ReadinessOptions`.**: The options say what a caller excuses, and each turns a blocker into an advisory (`merge_readiness.py:58-60`). Reading other data excuses no blocker. `get_pr_monitoring_status` passes no options today (`pr_monitor.py:540`), so the field would also need a new parameter.
- **Choose by `acts_as_github_app()`.**: It reads an environment variable (`core/process.py:286-293`), so the verdict would change with the process that runs it, and the call in `watch_pull` would show nothing of the choice. A test would set the variable. The issue asks that a test shows the choice, which a keyword in the call shows.
- **Add the `statuses` read permission to the App.**: AGENTS.md leaves repository settings to a person, and `git grep -n -i "statuses:\|/statuses\|commit-status" -- .github` finds no use of a commit status, so the grant would stay unused.
- **Make `_judge_checks` read check runs for every caller.**: `tests/github/test_merge_readiness.py:398` asserts that a failed combined status blocks, and `:442` asserts that a refused status read blocks. A person's `devops pr monitor` would no longer see a status that another tool sets.
- **Copy the check run read into `implement_pull.py`.**: `read_check_runs` already holds it, with the paging and the fail-closed rule.
