# release-urgent-merge Specification

## Purpose
When the release pull request of release-please merges without a person: an urgent fix, named by labels on its pull request or on the issues it closes, turns on GitHub auto-merge of the release pull request with the release App token.

## Requirements

### Requirement: An urgent fix turns on auto-merge of the release pull request
After `Run release-please`, the `release-please` job of `.github/workflows/release.yml` SHALL run `gh pr merge "$RELEASE_PR" --repo "$REPOSITORY" --auto --squash` in the step `Merge the Release Pull Request on an Urgent Fix` when the pull request of the pushed commit has the label `release-now`, or closes an issue labeled `priority/p0-critical`, or `type/security` with `priority/p1-high`.

#### Scenario: The step and its labels
- **WHEN** `.github/workflows/release.yml` is read
- **THEN** the step comes after `Run release-please`, its `RELEASE_PR` is `${{ fromJSON(steps.release.outputs.pr).number }}`, and its script names the four labels and runs `gh pr merge "$RELEASE_PR" --repo "$REPOSITORY" --auto --squash`

### Requirement: The release App token turns on the auto-merge, and only for an update
The step SHALL use the release App token, so the merge starts the `Release` run that creates the release. It SHALL not run in the run of a release merge or when release-please returned no release pull request.

#### Scenario: The token and the condition
- **WHEN** `.github/workflows/release.yml` is read
- **THEN** the step's `GH_TOKEN` is `${{ steps.app.outputs.token }}` and its condition is `steps.release.outputs.releases_created != 'true' && steps.release.outputs.pr != ''`

### Requirement: The urgent-fix rule is declared and documented
`.github/labels.yml` SHALL declare the label `release-now`, and `RELEASE_CYCLE.md` SHALL name `release-now`, `priority/p0-critical`, `type/security` and `priority/p1-high` in its rule.

#### Scenario: The label and the procedure
- **WHEN** `.github/labels.yml` and `RELEASE_CYCLE.md` are read
- **THEN** the label `release-now` is declared, and the procedure names each of the four labels
