## ADDED Requirements

### Requirement: A pinned commit takes the highest full release of its tags
For an Action pin with a commit and a version that names no full release, `devops research advisories` SHALL read the tags of the Action repository (`GET /repos/{owner}/{repo}/tags` on `api.github.com`) and SHALL use the highest full release tag that points to the commit. A full release tag SHALL hold a major, a minor and a patch number and no prerelease suffix, and a tag with fewer numbers or a prerelease suffix SHALL NOT be the release of a pin.

#### Scenario: The highest release of the commit wins
- **WHEN** the tags of `actions/checkout` hold `v7.2.0` and `v7.2.1` at the pinned commit, and `v7.3.0` at another commit
- **THEN** the pin takes the release `v7.2.1`

#### Scenario: A prerelease tag is no release
- **WHEN** the tags of the repository hold `v7.2.1-rc1` at the pinned commit and no other full release tag at it
- **THEN** the pin is counted in `unpinned`

### Requirement: The tags of an Action are read page by page
The command SHALL read the tags pages of an Action repository one after another until every pinned commit of that repository is found or the reply names no next page, and SHALL read no page after it finds them. A list longer than `DEFAULT_GITHUB_ADVISORIES_MAX_PAGES` pages SHALL be a failed read.

#### Scenario: The commit is on a later page
- **WHEN** the first tags page holds no tag of the pinned commit and the second page holds the full release `v7.2.1` at it
- **THEN** the pin takes the release `v7.2.1` and the command reads no third page

### Requirement: A commit with no full release stays unpinned
A pin whose commit has no full release tag SHALL be counted in `unpinned`, and the command SHALL match no advisory to it.

#### Scenario: No release tag for the commit
- **WHEN** the tags of the repository hold no full release tag at the pinned commit
- **THEN** the pin is counted in `unpinned` and no advisory is matched to it

### Requirement: A failed tags read is a failure and not a clean pin
When the tags read of an Action repository fails, or answers with a status that is no success, the report SHALL list one failure for each version that the pins of that repository name, with the Action repository and the reason, and the command SHALL exit with code 1. The pin SHALL NOT appear as a component without findings.

#### Scenario: The tags request fails
- **WHEN** the tags request of `actions/checkout` answers the status 500
- **THEN** the report holds a failure that names `actions/checkout` with the reason `GitHub returned status 500`, the pin has no finding, and the command exits with code 1

#### Scenario: Two pins of one repository and version
- **WHEN** two pins of `actions/checkout` at `v6` share a tags read that answers the status 500
- **THEN** the report holds one failure for `actions/checkout` at `v6`, and not one for each pin

### Requirement: The tags of one Action repository are read once in a run
The command SHALL read the tags of each Action repository at most once in a run, and SHALL read them only when a pin of that repository holds a commit and a version which names no full release.

#### Scenario: Two pins of one repository
- **WHEN** two pins of `actions/checkout` hold commits and the versions `v7` and `v6`
- **THEN** the command sends one tags request sequence for `actions/checkout`

#### Scenario: A sub-path Action
- **WHEN** the pin `github/codeql-action/init` holds a commit and the version `v4`
- **THEN** the command reads the tags of the repository `github/codeql-action`, and the pin keeps its full name with the release of its commit

#### Scenario: The plan of a dry run
- **WHEN** `devops research advisories --dry-run` runs on a repository whose pin holds a commit and the version `v7`
- **THEN** the plan lists one tags request for the Action repository and the command sends no request

## MODIFIED Requirements

### Requirement: Each GitHub Action with an exact release is checked against the GitHub advisories
`devops research advisories` SHALL read the reviewed GitHub advisories that name each GitHub Action of the inventory whose version names one release (`GET /advisories` with the ecosystem `actions` and the package names), and SHALL report one finding for each advisory whose range holds the pinned version. A pin whose commit resolves to a full release takes that release before the match. An Action whose pin names no one release SHALL be counted in `unpinned` and SHALL NOT be sent.

#### Scenario: A pinned release inside an affected range
- **WHEN** a workflow pins `tj-actions/changed-files` at `v45.0.0` and GitHub lists the advisory `GHSA-mrrh-fwg8-r2c3` with the range `<= 45.0.7` and the fix 46.0.1
- **THEN** the report holds a finding with the source `GitHub`, the severity `HIGH`, the alias `CVE-2025-30066`, the affected range `<= 45.0.7` and the fixed version `46.0.1`

#### Scenario: A pinned release after the fix
- **WHEN** a workflow pins `tj-actions/changed-files` at `v46.0.1`
- **THEN** the report holds no finding for that pin

#### Scenario: A major tag
- **WHEN** a workflow pins `actions/checkout` at the tag `v4` and the pin holds no commit that resolves to a full release
- **THEN** the pin is counted in `unpinned` and no advisory is matched to it

#### Scenario: A package name in the request
- **WHEN** the inventory holds the Actions `tj-actions/changed-files` and `actions/checkout`
- **THEN** one request names both packages in `affects`, and an advisory that names only one package is a finding for that package only
