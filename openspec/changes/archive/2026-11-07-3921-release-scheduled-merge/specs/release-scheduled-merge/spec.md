## Purpose

When the release pull request of release-please merges by itself on a schedule: every 6 hours the workflow `release-merge.yml` picks the pull request that passes every guard and squash-merges it with the release App token, and a person can hold it with a label.

## ADDED Requirements

### Requirement: The workflow runs every 6 hours with read-only permissions
`.github/workflows/release-merge.yml` SHALL run on `cron: "0 */6 * * *"` and on `workflow_dispatch` and on no other event. It SHALL have one job, the concurrency group `release-merge` without cancellation, no workflow-level permission, and the job permissions `contents: read`, `pull-requests: read` and `checks: read`.

#### Scenario: The trigger and the permissions
- **WHEN** `.github/workflows/release-merge.yml` is read
- **THEN** the triggers are the schedule `0 */6 * * *` and `workflow_dispatch`, the permissions are the three read permissions, and the group is `release-merge`

### Requirement: The pick reads and the merge step merges the picked commit
The step `Pick the Release Pull Request` SHALL run `python -m devops_cli.release.merge_candidate` with `GITHUB_TOKEN`. The step `Merge the Release Pull Request` SHALL run only when the pick printed a number, and SHALL run `gh pr merge "$NUMBER" --repo "$REPOSITORY" --squash --match-head-commit "$HEAD_SHA"`.

#### Scenario: The merge step
- **WHEN** `.github/workflows/release-merge.yml` is read
- **THEN** the merge step has the condition `steps.pick.outputs.number != ''` and the command above

### Requirement: Only the merge step gets the release App token
The step `Mint the Release App Token` SHALL ask for `contents: write` and `pull-requests: write` only. Only the step `Merge the Release Pull Request` SHALL read the token. No `run` script SHALL hold an expression, and no step SHALL push a branch or a tag, edit a pull request or make a release.

#### Scenario: The token reaches one step
- **WHEN** `.github/workflows/release-merge.yml` is read
- **THEN** the mint step has exactly those two permissions, the pick step has no reference to the token, the merge step has `GH_TOKEN: ${{ steps.app.outputs.token }}`, and no script holds `${{`

### Requirement: The pull request must be a release pull request of the release App
`devops_cli.release.merge_candidate` SHALL pick a pull request only when it is open and not a draft, its author is the release App, its head is a `release-please--branches--main` branch of the same repository, its base is `main`, its title is `chore(main): release <version>` with a version that parses, it has the label `autorelease: pending` and not `hold-release`, and GitHub reports it as mergeable.

#### Scenario: One guard fails
- **WHEN** a pull request fails exactly one of these guards
- **THEN** `refusals` returns one reason that names the guard

### Requirement: The pull request must change only the files that release-please writes
It SHALL pick a pull request only when every file it changes is `.release-please-manifest.json`, `CHANGELOG.md`, `pyproject.toml` or `uv.lock` with the status `modified`. A file that is added, removed or renamed, or any other path, SHALL refuse the merge.

#### Scenario: A source file in the pull request
- **WHEN** the pull request changes `src/devops_cli/main.py` besides `CHANGELOG.md`
- **THEN** `refusals` returns one reason that names the path

### Requirement: The checks must pass
It SHALL pick a pull request only when every check that the ruleset of `main` requires has the result `success` on its head commit, no other check failed there, and no required check failed on the head of `main`. When it cannot read the rules or the checks, or the rules name no required check, it SHALL pick none.

#### Scenario: A check fails
- **WHEN** a required check is not `success`, or a check that no rule requires failed, or a required check failed on the head of `main`
- **THEN** `refusals` returns one reason for each of them

### Requirement: A run picks at most one pull request and a failed read fails the run
It SHALL pick the lowest-numbered pull request that passes and no other. `main` SHALL print `number=<n>` and `sha=<head commit>` on standard output for a pick and nothing there otherwise. When GitHub cannot be read, `main` SHALL exit with status 1.

#### Scenario: Two release pull requests
- **WHEN** two pull requests with the label pass every guard
- **THEN** the pick returns the lower number and does not read the other

#### Scenario: A failed read is not a refusal
- **WHEN** GitHub answers a read with an error
- **THEN** `main` exits with status 1 and prints nothing on standard output

### Requirement: The files of the guard are the files that release-please writes
`RELEASE_FILES` SHALL equal the manifest, `CHANGELOG.md`, `pyproject.toml` and the extra files that `release-please-config.json` names.

#### Scenario: The guard follows the configuration
- **WHEN** `release-please-config.json` is read
- **THEN** its extra files and the files above are exactly `RELEASE_FILES`

### Requirement: A person holds a release with a label, and the rule is documented
`.github/labels.yml` SHALL declare `hold-release`. `RELEASE_CYCLE.md` SHALL name `release-merge.yml`, the cadence of 6 hours, `hold-release` and how to disable the workflow.

#### Scenario: The label and the procedure
- **WHEN** `.github/labels.yml` and `RELEASE_CYCLE.md` are read
- **THEN** the label is declared and the procedure names the workflow, the cadence, the label and **Disable workflow**
