## MODIFIED Requirements

### Requirement: An urgent fix turns on auto-merge of the release pull request
After `Run release-please`, the `release-please` job of `.github/workflows/release.yml` SHALL run `gh pr merge "$RELEASE_PR" --repo "$REPOSITORY" --auto --squash` in the step `Merge the Release Pull Request on an Urgent Fix` when the pull request of the pushed commit has the label `release-now`, or closes an issue labeled `priority/p0-critical`, or `scope/security` with `priority/p1-high`.

#### Scenario: The step and its labels
- **WHEN** `.github/workflows/release.yml` is read
- **THEN** the step comes after `Run release-please`, its `RELEASE_PR` is `${{ steps.release.outputs.pr }}`, its script names the four labels and not `type/security`, and it runs `gh pr merge "$RELEASE_PR" --repo "$REPOSITORY" --auto --squash`

### Requirement: The urgent-fix rule is declared and documented
`.github/labels.yml` SHALL declare the labels `release-now` and `scope/security`, and `RELEASE_CYCLE.md` SHALL name `release-now`, `priority/p0-critical`, `scope/security` and `priority/p1-high` in its rule.

#### Scenario: The label and the procedure
- **WHEN** `.github/labels.yml` and `RELEASE_CYCLE.md` are read
- **THEN** the labels `release-now` and `scope/security` are declared, and the procedure names each of the four labels
