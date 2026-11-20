## ADDED Requirements

### Requirement: An Action pin to a commit keeps its commit
The inventory SHALL keep, beside the version, the commit of an Action pin whose ref is a full commit sha, and SHALL keep no commit for any other pin.

#### Scenario: A pin to a commit and a major tag
- **WHEN** a step reads `uses: actions/checkout@<commit> # v7`
- **THEN** the version of the component is `v7` and the component holds the commit
