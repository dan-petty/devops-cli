# Tasks

## 1. The verdict keeps the kind of each blocker and its check read

- [x] Add failing tests: each blocker's kind, the check read the verdict keeps, and no blocker for a branch behind its base
  - Verification: `uv run devops ci test tests/test_merge_readiness.py`
- [x] Add `BlockerKind`, `Blocker`, `MergeReadiness.blocking` and `MergeReadiness.checks`; derive `MergeReadiness.blockers` from `blocking`
  - Verification: `uv run devops ci test tests/test_merge_readiness.py tests/commands/test_pr.py`

## 2. pr ready and pr monitor read the verdict

- [x] Add failing tests: the exit-code table of `pr ready` and `pr monitor`, the scripted monitor run that names the failed check and the thread, a missing priority label that only warns in `pr ready`, and a failed read that stops `pr ready`
  - Verification: `uv run devops ci test tests/commands/test_pr.py`
- [x] Make `fetch_pr_details` the one pull request read and delete `_fetch_pr_details` in `commands/pr.py`
  - Verification: `rg -n 'def _?fetch_pr_details' src`
- [x] Judge each monitor poll through the verdict and the review gate, wait while a check runs, and report every blocker; delete the monitor's own mergeable, draft, thread and check rules, `PRCheckRun`, and their tests
  - Verification: `uv run devops ci test tests/test_github_pr_monitor.py tests/commands/test_pr.py`
- [x] Map the verdict to `pr ready`'s exit codes; delete its check-verdict rendering and the readiness tests that patch `devops_cli.commands.pr.run_gh`
  - Verification: `uv run devops ci test tests/test_pr_cmd.py tests/commands/test_pr.py`
- [x] Describe the new monitor behavior in the command help, and regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 3. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 2443-pr-ready-monitor-verdict`
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
