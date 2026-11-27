## ADDED Requirements

### Requirement: A release is published only after its images are tagged
The job `Upload Release Assets` SHALL start only after each job of the `Release` run that pushes or tags an image passed: `Build DevContainer Image`, `Smoke-Test DevContainer Image`, `Attest & Tag DevContainer Image`, and the `Build`, `Verify` and `Attest & Tag` jobs of each image of `release-image.yml`. A failed or skipped image job SHALL leave the release a draft. "Re-run failed jobs" SHALL publish the release when the failed jobs pass.

#### Scenario: The images are tagged before the publication
- **WHEN** the `Release` run of a release merge ends with each job passed
- **THEN** the live check `devops gh api repos/dan-petty/devops-cli/actions/runs/<run>/jobs --jq '[.jobs[] | select(.name | test("Attest & Tag")) | .completed_at] | max'` gives a time earlier than the live check `devops gh api repos/dan-petty/devops-cli/releases/tags/<tag> --jq .published_at`

#### Scenario: A failed image job keeps the draft
- **WHEN** an image job of the `Release` run of a release merge fails
- **THEN** the job `Upload Release Assets` is skipped, and the live check `devops gh api repos/dan-petty/devops-cli/releases/tags/<tag> --jq .draft` gives `true`

#### Scenario: A re-run publishes the draft
- **WHEN** a person clicks **Re-run failed jobs** on that run and the failed jobs pass
- **THEN** the job `Upload Release Assets` runs, and the live check `devops gh api repos/dan-petty/devops-cli/releases/tags/<tag> --jq .draft` gives `false`

#### Scenario: The job graph
- **WHEN** a maintainer runs `uv run devops ci --check --only actionlint,zizmor` on `.github/workflows/release.yml`
- **THEN** both checks pass, and the `needs` of the job `assets` hold each job of `release.yml` with the permission `packages: write`
