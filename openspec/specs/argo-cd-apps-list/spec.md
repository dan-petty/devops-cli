# argo-cd-apps-list Specification

## Purpose
The Repo column of devops argo cd apps list shows the source repository URL for each Application, including multi-source Applications that use spec.sources.

## Requirements

### Requirement: single-source-repo-shown
When an Application has spec.source.repoURL set, the Repo column SHALL show that URL.

#### Scenario: Application with spec.source set
- **WHEN** An Application JSON has spec.source.repoURL set to a value and spec.sources absent
- **THEN** The Repo column shows the value of spec.source.repoURL

### Requirement: multi-source-first-repo-shown
When an Application has spec.sources and no spec.source, the Repo column SHALL show the repoURL of the first element of spec.sources.

#### Scenario: Application with spec.sources list
- **WHEN** An Application JSON has spec.sources as a non-empty list and spec.source absent
- **THEN** The Repo column shows the repoURL of spec.sources[0]

### Requirement: no-source-empty-repo
When an Application has neither spec.source nor spec.sources, the Repo column SHALL be an empty string.

#### Scenario: Application with no source fields
- **WHEN** An Application JSON has neither spec.source nor spec.sources
- **THEN** The Repo column is an empty string
