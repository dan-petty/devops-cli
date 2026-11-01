## Purpose
The Repo column of `devops argo cd apps list` names the source repository of each Argo CD Application. This capability fixes which source the column shows when an Application has one source, several sources or none, and that the help of the command states the rule.

## ADDED Requirements

### Requirement: Single-source repository shown
When an Application has `spec.source.repoURL` and no `spec.sources`, the Repo column SHALL show that URL.

#### Scenario: Application with spec.source set
- **WHEN** an Application has `spec.source.repoURL` set to a value and `spec.sources` absent
- **THEN** the Repo column shows the value of `spec.source.repoURL`

### Requirement: First source shown for an Application with several sources
When an Application has a non-empty `spec.sources`, the Repo column SHALL show the `repoURL` of the first entry of `spec.sources`, as Argo CD uses `spec.sources` before `spec.source`.

#### Scenario: Application with spec.sources and no spec.source
- **WHEN** an Application has `spec.sources` as a list of two entries with different `repoURL` values and `spec.source` absent
- **THEN** the Repo column shows the `repoURL` of the first entry and not the `repoURL` of the second

#### Scenario: Application with both spec.source and spec.sources
- **WHEN** an Application has `spec.source.repoURL` set and a non-empty `spec.sources`
- **THEN** the Repo column shows the `repoURL` of the first entry of `spec.sources`

### Requirement: Empty repository when no source is set
When an Application has neither `spec.source` nor a usable `spec.sources`, the Repo column SHALL be empty, and the command SHALL NOT fail.

#### Scenario: Application with no source fields
- **WHEN** an Application has neither `spec.source` nor `spec.sources`
- **THEN** the Repo column is empty

#### Scenario: Application with a malformed source field
- **WHEN** an Application has no `spec.source`, and a `spec.sources` that is not a list or whose first entry is not an object
- **THEN** the Repo column is empty and the command lists the other Applications

### Requirement: Help states which source the Repo column shows
The help of `devops argo cd apps list` SHALL state that the Repo column shows the first source of an Application that has several sources.

#### Scenario: Help of the list command
- **WHEN** the user runs `devops argo cd apps list --help`
- **THEN** the output says that the Repo column shows the first source of an Application with several sources
