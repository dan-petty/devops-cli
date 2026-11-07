# Tasks

## 1. The guards pick the release pull request that may merge (behavior)

- [x] 1.1 Add failing tests of every guard (`refusals`), of the pick over the `github_api` fake, of `main`, and of `RELEASE_FILES` against `release-please-config.json`
  - Verification: `uv run devops ci test tests/release/test_release_merge_guards.py tests/release/test_release_merge_pick.py`
- [x] 1.2 Add `src/devops_cli/release/merge_candidate.py` and the messages of `ReleaseMessages`
  - Verification: `uv run devops ci test tests/release/test_release_merge_guards.py tests/release/test_release_merge_pick.py`

## 2. The workflow merges the picked pull request every 6 hours (workflow)

- [x] 2.1 Add the contract tests of the trigger, the permissions, the token and the scripts to `tests/invariants/test_workflow_contracts.py`, and let the cache test of `tests/commands/test_ci.py` treat `release-merge.yml` like `release.yml`: it holds a write token, so it restores no cache
  - Verification: `uv run devops ci test tests/invariants/test_workflow_contracts.py tests/commands/test_ci.py`
- [x] 2.2 Add `.github/workflows/release-merge.yml` and the label `hold-release` to `.github/labels.yml`
  - Verification: `uv run devops scan workflows`

## 3. The documents state the scheduled merge (documents)

- [x] 3.1 Write the scheduled merge, the guards, the hold label and the way to turn it off in `RELEASE_CYCLE.md`. Add the one exception to `AGENTS.md`. Amend ADR 0013. Fix the documents that say that only a person merges the release pull request
  - Verification: `uv run devops ci docs`

## 4. Archive

- [x] 4.1 Archive the change
  - Verification: `uv run devops openspec archive 3921-release-scheduled-merge`
- Pending a person: run `devops gh labels sync` after the merge, so the label `hold-release` exists in the repository.
- Pending a person: at the first scheduled run, or after **Run workflow**, read the log of the step `Pick the Release Pull Request`. When a pull request merges, check that the `Release` run starts and creates the release.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
