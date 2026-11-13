## ADDED Requirements

### Requirement: The pick reads the files from the compare of the base branch
It SHALL read the files of a pull request from the compare of its base branch and its head commit, the diff that the squash merge applies. It MUST NOT read the pulls files list, because GitHub can keep a stale `base.sha` after the merge base moved, and then that list holds files of `main`.

#### Scenario: A stale base sha
- **WHEN** the payload `base.sha` of a release pull request is not the merge base, and its pulls files list holds a file of `main` beside the release files
- **THEN** the pick reads the compare of `main` and the head commit, sends no pulls files request, and picks the pull request
