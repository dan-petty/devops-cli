## ADDED Requirements

### Requirement: The package declares the workflow labels
The package SHALL declare each label that the roadmap code reads or writes, with its color and description. `.github/labels.yml` SHALL hold only the labels of its repository. A reader of the file SHALL get the workflow labels first, then each file label that no workflow label names. Each label color SHALL be a design token color.

#### Scenario: Every written label is declared
- **WHEN** a test collects the field labels, the type labels, `source/agent` and `plan/needs-fix` from the constants
- **THEN** the package list holds each of them

#### Scenario: The labels file holds no workflow label
- **WHEN** a test reads `.github/labels.yml` of devops-cli
- **THEN** it holds no `type/`, `status/`, `priority/`, `value/`, `effort/`, `owner/`, `review/`, `plan/` or `source/` label

#### Scenario: A file label that names a workflow label
- **WHEN** a labels file holds `scope/cli` and `status/new` with the color `FFFFFF`
- **THEN** the reader gives the workflow labels, then `scope/cli`, and `status/new` keeps the color of the package

## MODIFIED Requirements

### Requirement: One label family holds the owner of an Item
The roadmap store SHALL read an Item's Owner from the family `owner/service`, `owner/agent` and `owner/human`, and SHALL write it with the rules of the other fields: a job replaces the family, the record names the value the job set, and a write raises `RoadmapItemChangedError` when someone changed the owner since the store read it. An Item with no label of the family SHALL have no owner. The package SHALL declare the label of every value of every field.

#### Scenario: An issue with an owner label
- **WHEN** an issue holds `priority/p2-medium` and `owner/agent`
- **THEN** its Item has the Owner `Agent`

#### Scenario: A person adds a label to a claim of the Service
- **WHEN** a job set the Owner `Service`, and a person adds `owner/human` and leaves `owner/service`
- **THEN** the next read gives the Item the Owner `Human`

#### Scenario: A person changed the owner after the read
- **WHEN** a job read an Item with no owner, a person then set `owner/human`, and the job sets the Owner `Service`
- **THEN** the write raises `RoadmapItemChangedError` and the issue holds `owner/human`

#### Scenario: The labels file declares the labels
- **WHEN** a test reads `.github/labels.yml` through `declared_label_specs`
- **THEN** it gets `owner/service`, `owner/agent`, `owner/human` and the label of every value of Status, Priority, Value and Effort, from the package

### Requirement: The Status family has six labels
The Status family SHALL hold `status/new`, `status/ready`, `status/planned`, `status/in-progress`, `status/in-review` and `status/blocked`, in this order. The package SHALL declare each of them.

#### Scenario: The labels file
- **WHEN** a test reads `.github/labels.yml` through `declared_label_specs`
- **THEN** it gets all six `status/*` labels, from the package

#### Scenario: A Planned issue
- **WHEN** an issue holds `status/planned`
- **THEN** its Item has the Status `Planned`
