## MODIFIED Requirements

### Requirement: The package declares the workflow labels
The package SHALL declare each label that the roadmap code reads or writes, with its color and description. `.github/labels.yml` SHALL hold only the labels of its repository. A reader of the file SHALL get the workflow labels first, then each file label that no workflow label names. Each label color SHALL be a design token color.

#### Scenario: Every written label is declared
- **WHEN** a test collects the field labels, the type labels, `source/agent` and `verdict/fix-plan` from the constants
- **THEN** the package list holds each of them

#### Scenario: The labels file holds no workflow label
- **WHEN** a test reads `.github/labels.yml` of devops-cli
- **THEN** it holds no `type/`, `status/`, `priority/`, `value/`, `effort/`, `owner/`, `review/`, `plan/`, `verdict/` or `source/` label

#### Scenario: A file label that names a workflow label
- **WHEN** a labels file holds `scope/cli` and `status/new` with the color `FFFFFF`
- **THEN** the reader gives the workflow labels, then `scope/cli`, and `status/new` keeps the color of the package
