# Proposal

## Why

Issue #7220: `.github/workflows/ci.yml` runs no test shard for a pull request from a `release-please--` branch, so the required check `Tests & Coverage` comes from the push run of `main`, and a commit that a write-access session pushes to the release branch merges with no test of its own tree. Only release-please must write that branch, so the job `Tests on Main` must refuse a release pull request that changes any other file.

## What Changes

- `src/devops_cli/release/merge_candidate.py` gains `release_file_refusals(session, repository, number)` and `_file_refusals` takes the number and the changed files, so the release-please file set has one owner.
- `src/devops_cli/release/release_files.py` runs the guard as a command: it exits 1 with one reason for each path outside the set or when GitHub cannot be read, and exits 0 for a clean release pull request.
- `src/devops_cli/lang/en/messages.py` holds the usage of `--pull` and the line of a clean pull request.
- `.github/workflows/ci.yml` runs the guard in the job `Tests on Main` from the base commit, before the wait for the push run of `main`, so a foreign path fails the required check `Tests & Coverage`.
- `RELEASE_CYCLE.md` says that the job `Tests on Main` refuses a path that release-please does not write.
- The spec delta of `release-scheduled-merge` adds the release check and the job that runs it.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `release-scheduled-merge`: The release check refuses a file outside the release set, The job Tests on Main runs the release check from the base commit

## Impact

- Code: `src/devops_cli/release/merge_candidate.py`, `src/devops_cli/release/release_files.py`, `src/devops_cli/lang/en/messages.py`, `.github/workflows/ci.yml`
- Documents: `RELEASE_CYCLE.md`
- Tests: `tests/release/test_release_files.py`

## Feasibility

- Probe line, word for word: The path `ci.yml` is no file at the root of the staging commit. These files of the commit are candidates: `.github/workflows/ci.yml`, `tests/fixtures/research/advisories/github_repo/.github/workflows/ci.yml`, `tests/fixtures/research/repo/.github/workflows/ci.yml`. No commit in the history deleted or renamed it. The workflow of the issue is `.github/workflows/ci.yml:348:main-tests:`, the job that the plan changes.
- Probe line, word for word: The path `release.yml` is no file at the root of the staging commit. These files of the commit are candidates: `.github/workflows/release.yml`. No commit in the history deleted or renamed it. `.github/workflows/release-merge.yml:72:uv run --locked --no-dev python -m devops_cli.release.merge_candidate \` shows the guard command of the scheduled merge.
- Probe line, word for word: The path `devops_cli.release.merge_candidate` is no file of the staging commit. No commit in the history deleted or renamed it. The dotted name is the module `src/devops_cli/release/merge_candidate.py:46:BASE_BRANCH: Final[str] = "main"`.
- Probe line, word for word: The path `AGENTS.md` is a file of the staging commit. `AGENTS.md` gives a repository setting to a person, so this plan adds no push ruleset.
- `read_file` of `.github/workflows/ci.yml` this run showed the skipped shard: `.github/workflows/ci.yml:147:&& !(startsWith(github.head_ref, 'release-please--')`.
- `read_file` of `.github/workflows/ci.yml` this run showed that the required check needs the job: `.github/workflows/ci.yml:243:needs: [test-shard, main-tests]` and `.github/workflows/ci.yml:266:if: needs.test-shard.result != 'success' && needs.main-tests.result != 'success'`.
- `read_file` of `.github/workflows/ci.yml` this run showed the job to change: `.github/workflows/ci.yml:348:main-tests:`, its one permission `.github/workflows/ci.yml:357:actions: read # reads the push run of main and its jobs`, its step `.github/workflows/ci.yml:360:- name: Read Tests & Coverage of Main`, and the base commit it reads `.github/workflows/ci.yml:365:BASE_SHA: ${{ github.event.pull_request.base.sha }}`.
- `read_file` this run showed the file guard at `src/devops_cli/release/merge_candidate.py:149:def _file_refusals(facts: ReleaseFacts) -> list[str]:`, its refusal line at `src/devops_cli/release/merge_candidate.py:160:if path not in RELEASE_FILES or changed.status != "modified":`, and its caller at `src/devops_cli/release/merge_candidate.py:210:return [*_pull_refusals(facts), *_file_refusals(facts), *_check_refusals(facts)]`.
- `read_file` this run showed the compare read, its caller and the command form: `src/devops_cli/release/merge_candidate.py:247:def _changed_files(`, `src/devops_cli/release/merge_candidate.py:253:compared = session.client.get_compare_files(repository, pull.base_ref, pull.head_sha)`, `src/devops_cli/release/merge_candidate.py:283:files=_changed_files(session, repository, pull),` and `src/devops_cli/release/merge_candidate.py:302:parser = argparse.ArgumentParser(prog="python -m devops_cli.release.merge_candidate")`.
- The staged constants that the plan relies on: `src/devops_cli/release/merge_candidate.py:53:RELEASE_FILES: Final[frozenset[str]] = frozenset(` holds `src/devops_cli/release/merge_candidate.py:54:{".release-please-manifest.json", "CHANGELOG.md", "pyproject.toml", "uv.lock"}`, and `src/devops_cli/release/merge_candidate.py:46:BASE_BRANCH: Final[str] = "main"`.
- The set of release files has 4 members, from `src/devops_cli/release/merge_candidate.py:54:{".release-please-manifest.json", "CHANGELOG.md", "pyproject.toml", "uv.lock"}`. The plan adds no member, so each member stays allowed while the pull request modifies it, and each other path is refused.
- The proof that the issue asks for already exists: `tests/release/test_release_merge_guards.py:147:_modified("CHANGELOG.md", "src/devops_cli/main.py"),` in `tests/release/test_release_merge_guards.py:155:def test_a_file_that_release_please_does_not_write_keeps_the_release_from_merging(`. Group 1 adds no second copy of that refusal and tests the new command instead.
- `references` for `_file_refusals` found one file and two lines, `src/devops_cli/release/merge_candidate.py:149:def _file_refusals(facts: ReleaseFacts) -> list[str]:` and `src/devops_cli/release/merge_candidate.py:210:return [*_pull_refusals(facts), *_file_refusals(facts), *_check_refusals(facts)]`, and that file is in the `changes` of group 1.
- `read_file` this run showed the release texts at `src/devops_cli/lang/en/messages.py:7561:class ReleaseMessages:`, with the refusal `src/devops_cli/lang/en/messages.py:7578:refusal_file: str = (` and the usage `src/devops_cli/lang/en/messages.py:7601:usage_repo: str = "The repository to read, as owner/name."`.
- `read_file` this run showed the session entry point at `src/devops_cli/github/session.py:194:def get_github_session() -> GitHubSession:`.
- Precondition of `get_github_session()` at `src/devops_cli/github/session.py:194:def get_github_session() -> GitHubSession:`: a client of the GitHub service, whose identity the function reads from the environment, and a network.
- Precondition of `_changed_files(session, repository, pull)` at `src/devops_cli/release/merge_candidate.py:247:def _changed_files(`: a client of the GitHub service and a network, because `src/devops_cli/release/merge_candidate.py:253:compared = session.client.get_compare_files(repository, pull.base_ref, pull.head_sha)` reads the compare.
- Precondition of `release_file_refusals(session, repository, number)`: a client of the GitHub service and a network, because it reads the pull request and calls `_changed_files`; a test gives the session of `tests/support/fakes/github.py:504:def github_api(` and reaches no network.
- Precondition of `check_release_files(argv)` of the new command module: a checkout of the repository, because the step runs `python -m devops_cli.release.release_files` in it, a client of the GitHub service and a network; the module takes its session from `get_github_session()`, so a test passes a fake session instead.
- `read_file` this run showed the fake GitHub API and the assertion pattern that the new test follows: `tests/release/test_release_merge_pick.py:192:assert main(["--repo", REPO, "--app-login", APP]) == 0`, with `tests/support/fakes/github.py:203:def route_compare_files(` and `tests/support/fakes/github.py:504:def github_api(`.
- The new checkout keeps the contract of `tests/invariants/test_workflow_contracts.py:def test_every_checkout_states_its_credentials_and_only_a_pushing_job_keeps_them`, so it states `persist-credentials: false`, and the pinned action keeps `tests/invariants/test_workflow_contracts.py:def test_every_remote_action_is_pinned_to_a_commit_sha`. The step puts its values in `env:`, as `tests/invariants/test_workflow_contracts.py:def test_no_run_block_interpolates_an_actions_expression` requires, and its `timeout-minutes: 5` stays under the job limit that `tests/invariants/test_workflow_contracts.py:def test_every_job_has_a_limit_and_each_step_limit_is_under_it` checks.
- `read_file` this run showed the text that group 3 updates: `RELEASE_CYCLE.md:10:4. The release pull request shows the same required checks as every pull request.` and the row `RELEASE_CYCLE.md:24:| Files | It changes only `.
- `find_issues` for `release-please branch guard Tests on Main` listed this item and its draft plan beside items of other areas, so no open item changes this guard.
- `read_issue` for #842 answered `#842 issue, closed (completed)`, and that item set required status checks through rulesets, so it is no dependency of this change.
- First checks against the real system: `uv run devops ci test tests/release/test_release_files.py tests/release/test_release_merge_guards.py tests/release/test_release_merge_pick.py` after group 1, `uv run devops ci --check --only actionlint,zizmor` after group 2, and the live read `uv run --locked --no-dev python -m devops_cli.release.release_files --repo dan-petty/devops-cli --pull <number of the open release pull request>` with `GH_TOKEN`, which must exit 0 on the open release pull request.
- Runner capability of the verifies: `uv run devops ci test` runs `uv`, `python`, `pytest` and `devops` from the runner image, `uv run devops ci --check --only actionlint,zizmor` runs `actionlint` and `zizmor` from the image, and `uv run devops ci docs` runs the `docs` row of `devops`. No program of the plan is NOT_IN_RUNNER.
- Failure class of the verifies: each command exits 1 on a failed test, a finding of `actionlint` or `zizmor`, or a document that is not current, and the job reads that exit status. The pod keeps `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, the dropped capabilities `ALL` and the `RuntimeDefault` seccomp profile, and every verify needs no capability beyond them.

## Existing Tool Considered

danger/danger-js (MIT, active 2026-10-26) fails a pull request whose changed files leave an allowlist, but it gates the merge only, adds a Node toolchain beside the uv workflow and brings no release-please file set. The change reuses the guard at `src/devops_cli/release/merge_candidate.py:149:def _file_refusals(facts: ReleaseFacts) -> list[str]:` and adds one small module and one test: 15k tokens and 2 hours to build, keep and fix. It deletes no internal code.

## Dependencies

None.
