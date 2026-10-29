## MODIFIED Requirements

### Requirement: An urgent fix turns on auto-merge of the release pull request
After `Run release-please`, the `release-please` job of `.github/workflows/release.yml` SHALL run `gh pr merge "$RELEASE_PR" --repo "$REPOSITORY" --auto --squash` in the step `Merge the Release Pull Request on an Urgent Fix` when the pull request of the pushed commit has the label `release-now`, or closes an issue labeled `priority/p0-critical`, or `type/security` with `priority/p1-high`.

#### Scenario: The step and its labels
- **WHEN** `.github/workflows/release.yml` is read
- **THEN** the step comes after `Run release-please`, its `RELEASE_PR` is `${{ steps.release.outputs.pr }}`, and its script names the four labels and runs `gh pr merge "$RELEASE_PR" --repo "$REPOSITORY" --auto --squash`
