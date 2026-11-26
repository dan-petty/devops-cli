# Design

## Decisions

- **Run the file guard in the job `Tests on Main` of `.github/workflows/ci.yml`.**: The required check `Tests & Coverage` already needs that job at `.github/workflows/ci.yml:243:needs: [test-shard, main-tests]`, so a refusal there fails the required check.
- **Run the guard from a checkout of the base commit of the pull request.**: A write session pushes the head commit, so the guard code and its file set must come from the base commit, and a commit on the release branch cannot change the guard that refuses it.
- **Reuse the file guard and expose it as `release_file_refusals(session, repository, number)`.**: `src/devops_cli/release/merge_candidate.py:53:RELEASE_FILES: Final[frozenset[str]] = frozenset(` is the one set of release files, and a second list in the workflow would drift from it.
- **Run the guard as `python -m devops_cli.release.release_files`, as `src/devops_cli/release/merge_candidate.py:302:parser = argparse.ArgumentParser(prog="python -m devops_cli.release.merge_candidate")` does.**: The step needs no new `devops` command, no row of the command reference and no new dependency, and the fake GitHub API of `tests/support/fakes/github.py` tests it offline.
- **Read the changed files from the compare of `main` and the head commit.**: `src/devops_cli/release/merge_candidate.py:253:compared = session.client.get_compare_files(repository, pull.base_ref, pull.head_sha)` already does this, because the pulls file list can hold files of `main` after the merge base moved (#5388).
- **Put the guard step before the step `Read Tests & Coverage of Main`.**: A foreign path then fails the job in about a minute, not after a wait of up to 35 minutes.
- **Keep the automatic merge of a clean release pull request.**: A clean pull request changes only the four release files, so the guard exits 0 and `Tests on Main` keeps its result.
- **Add the file guard and leave the push ruleset of the issue to a person.**: `AGENTS.md` gives a repository setting to a person, and the guard refuses a release pull request that changes any path outside the four release files, read from the base commit. A commit that also edits `.github/workflows/ci.yml` remains for that ruleset, because GitHub takes the workflow definition of a `pull_request` run from the head commit. A commit that changes only the content of one of the four release files also remains for that ruleset, because the guard reads the path and the status of each file and not its content.
- **Test the new command in a new module and reuse the existing case of `refusals` for a path under `src/`.**: `tests/release/test_release_merge_guards.py:147:_modified("CHANGELOG.md", "src/devops_cli/main.py"),` already holds that case, so the new test covers the command and its exit status instead of a second copy of the refusal.

## Rejected alternatives

- **A push ruleset on `release-please--**` that allows only the release App.**: `AGENTS.md` gives a repository setting to a person, so the item would wait on a person and no test can assert the rule. `read_issue` for #842 answered `#842 issue, closed (completed)`, and that item asked for required status checks, not a file policy.
- **A `dorny/paths-filter` step in the workflow with its own list of the release files.**: The list would be a second copy of `src/devops_cli/release/merge_candidate.py:53:RELEASE_FILES: Final[frozenset[str]] = frozenset(`, and the workflow would carry no refusal text.
- **Check out the head commit of the release pull request and run the guard from it.**: A write session pushes that commit, so the guard code would come from the tree under test. The rule at `src/devops_cli/release/merge_candidate.py:160:if path not in RELEASE_FILES or changed.status != "modified":` must come from the base commit.
- **Add a second test of `refusals` with one file under `src/`.**: `tests/release/test_release_merge_guards.py:147:_modified("CHANGELOG.md", "src/devops_cli/main.py"),` already covers that refusal, so the new test covers the command instead.

## Unchanged references

- `tests/release/test_release_merge_guards.py` (import): It imports `refusals`, `RELEASE_FILES`, `ReleaseFacts` and `ReleasePull`, whose names and behavior stay.
- `tests/release/test_release_merge_pick.py` (import): It imports `pick` and `main`, which keep their signatures and call the changed guard inside `src/devops_cli/release/merge_candidate.py`.

## Security

The guard step crosses one trust boundary: it reads GitHub with the token of the job, which gains only `contents: read` and `pull-requests: read`, and it runs `python -m devops_cli.release.release_files` from a checkout of the base commit, so no code of the release pull request runs in the job. The checkout keeps `persist-credentials: false`, so the token stays out of `.git/config`, and the job keeps no write permission. A person confirms that `RELEASE_FILES` still names the files that release-please writes beside `release-please-config.json`. `tests/release/test_release_files.py::test_the_check_refuses_a_source_file` fails if the guard accepts a path under `src/`, and `uv run devops ci --check --only actionlint,zizmor` fails if the job gains a write permission or a new trigger.
