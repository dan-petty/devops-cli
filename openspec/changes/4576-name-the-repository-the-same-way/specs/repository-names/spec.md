## ADDED Requirements

### Requirement: A round span names its repository with the VCS attributes
A span that a Service round opens SHALL carry `vcs.provider.name`, `vcs.owner.name` and `vcs.repository.name` from the reference of the round, and SHALL NOT carry `service.repo`.

#### Scenario: A round span names its repository
- **WHEN** a `RepoWorker` round runs for `dan-petty/devops-cli` in `src/devops_cli/server/service.py`
- **THEN** the span holds `vcs.provider.name=github`, `vcs.owner.name=dan-petty` and `vcs.repository.name=devops-cli`, and no `service.repo` attribute

### Requirement: A Service metric names its repository by the casefolded key
The `repo` label of a `devops_cli_service_*` metric SHALL be the casefolded `RepoRef` key of the repository, or `other` for a repository that `service.repos` does not hold; `ServiceManager` SHALL hold `service.repos` as casefolded keys, so no metric of the Service carries the GitHub spelling of a repository.

#### Scenario: A configured repository keeps one label value
- **WHEN** a `ServiceManager` starts in `src/devops_cli/server/service.py` with `service.repos` holding `Example-Org/Repo1`
- **THEN** the primed `repo` labels hold `example-org/repo1` and no `Example-Org/Repo1`

#### Scenario: A metric for a repository outside service.repos
- **WHEN** a `RepoWorker` of a repository that `service.repos` does not hold runs one round, with the value of `RepoRef.metric_value` in `src/devops_cli/github/repo_ref.py`
- **THEN** its `repo` label is `other`
