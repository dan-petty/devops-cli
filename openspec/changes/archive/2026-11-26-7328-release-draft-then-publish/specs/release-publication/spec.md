## Purpose

The order in which the `Release` run creates a release, attaches its files and publishes it, on a repository with immutable releases.

## ADDED Requirements

### Requirement: A release is published only after its files are attached
release-please SHALL create the GitHub release as a draft. The job `Upload Release Assets` SHALL attach the wheel, the sdist and `SHA256SUMS.txt` to the draft, and SHALL publish the release only after the upload passes.

#### Scenario: A release with its files
- **WHEN** the `Release` run of a release merge ends with each job passed
- **THEN** the live check `devops gh api repos/dan-petty/devops-cli/releases/latest --jq '[.draft, .immutable, (.assets | length)]'` gives `[false,true,3]`

#### Scenario: A failed upload
- **WHEN** the upload of the job fails
- **THEN** the step ends before the publication, and the live check `devops gh api repos/dan-petty/devops-cli/releases --jq '.[0].draft'` gives `true`

### Requirement: The tag of a release exists before its publication
release-please SHALL create the git tag of a release at the commit of the release when it creates the draft.

#### Scenario: A draft has its tag
- **WHEN** the `Release` run of a release merge created the draft
- **THEN** the live check `devops gh api repos/dan-petty/devops-cli/git/ref/tags/<tag> --jq .object.sha` gives the commit of the release merge
