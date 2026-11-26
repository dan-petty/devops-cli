## ADDED Requirements

### Requirement: A tree with no SLO folder is said
When the environment tree has no `devops/monitoring/slos/`, `devops k8s catalog` SHALL warn on standard error that it names that folder and that the catalog holds no SLO.

#### Scenario: A tree with no SLO folder
- **WHEN** `devops k8s catalog --format json` runs on a fixture tree with no `devops/monitoring/slos/`
- **THEN** it exits 0, names the folder on standard error, and its JSON holds an empty list of SLOs

## MODIFIED Requirements

### Requirement: Description sources
The catalog command SHALL take each service description from its UI annotation, else from its `description` in `catalog.toml` of the environment tree, else show `none`.

#### Scenario: Three description sources
- **WHEN** the fixture has one service with an annotation, one service with a catalog `description` and no UI, and one service with neither
- **THEN** the three rows show the annotation text, the catalog text and `none`
