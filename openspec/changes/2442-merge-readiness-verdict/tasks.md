# Tasks

## 1. The item rules are public predicates in roadmap/

- [x] Add failing table tests: each rule names what is missing or nothing, an archived change passes, each missing archive names the folder, and each way a PR is ungrounded is one blocker
  - Verification: `uv run devops ci test tests/test_item_grounding.py`
- [x] Move the item rules and their facts into `src/devops_cli/roadmap/grounding.py` with public names
  - Verification: `uv run devops ci test tests/test_item_grounding.py`

## 2. One merge-readiness verdict in github/

- [x] Add failing tests of the verdict over the two GitHub edges, and the `github_api_and_gh` support fixture
  - Verification: `uv run devops ci test tests/test_merge_readiness.py`
- [x] Add `src/devops_cli/github/merge_readiness.py`; make `read_commit_checks` public with an injectable session, and give `list_pr_review_threads` an optional runner
  - Verification: `uv run devops ci test tests/test_merge_readiness.py tests/test_github_pr_threads.py tests/test_github_pr_monitor.py`
- [x] Describe the fixture in `docs/TESTING.md`
  - Verification: `uv run devops docs generate --sync-readme`

## 3. check-readiness renders the verdict

- [x] Add a failing CLI table test of the exit code and the line of each case, auto-resolve and the perimeter warning
  - Verification: `uv run devops ci test tests/commands/test_pr.py`
- [x] Make `check_readiness` render the verdict, and delete the readiness block of `commands/pr.py` and `_classify_check_run`
  - Verification: `uv run devops ci test tests/commands/test_pr.py tests/test_pr_cmd.py`
- [x] Delete the replaced readiness tests, `tests/test_pr_check_runs.py` and the `routed_session` fixture
  - Verification: `uv run devops ci test tests/test_pr_cmd.py`
- [x] Point `docs/SELF_IMPROVEMENT.md` at the perimeter advisory, and regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 4. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 2442-merge-readiness-verdict`

## Workflow follow-up

- #2443: `devops pr ready` and `devops pr monitor` read the verdict, and the monitor waits until the checks settle and names every blocker.
- #1324: the rest of the `devops pr` tests move onto edge fakes, among them the thread tests that patch `pr_threads.run_gh`.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
