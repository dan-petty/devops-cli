## MODIFIED Requirements

### Requirement: Only exact pins of packages are asked
The command SHALL send OSV the name, the version and the OSV ecosystem (`PyPI` or `npm`) of a package component with an exact version. It SHALL count a package whose version is empty or is not a version in `unpinned`, and SHALL NOT send it. It SHALL NOT send OSV an image, a chart, an action, a Terraform provider or a devcontainer feature.

#### Scenario: A pin that is a range
- **WHEN** `pyproject.toml` declares `pyyaml>=5.3` and `idna==3.6`
- **THEN** OSV is asked about `idna` only, and the summary counts one pin in `unpinned`

#### Scenario: Components that OSV cannot match
- **WHEN** the repository pins images and charts that the watch list does not map
- **THEN** none of them is in a query, and the summary counts each of them under its ecosystem

### Requirement: A component that no source matches is counted
The command SHALL count a component that no source matches in `not_covered` under its ecosystem. It SHALL NOT count an Action or a mapped component there.

#### Scenario: Not covered
- **WHEN** the repository pins a chart and an image that the watch list does not map, and an Action
- **THEN** the summary counts the chart under `helm` and the image under `docker`, and does not count the Action

## REMOVED Requirements

### Requirement: The watch list is checked
**Reason**: It held each release binary of `tools.lock` to an entry, and the lock is gone (#4363).
**Migration**: The requirement below keeps the checks of the file.

## ADDED Requirements

### Requirement: The watch list file is checked
Reading the watch list SHALL be an error that names the file when it is not valid TOML, has an unknown key, has a repository that is not `owner/name`, or maps a Python package, a Node package or an Action.

#### Scenario: A file that is wrong
- **WHEN** an entry has the repository `qdrant`, an unknown key, or the ecosystem `pypi`
- **THEN** reading the watch list is an error that names `.devops/research-watch.toml`
