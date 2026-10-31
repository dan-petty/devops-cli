# Spec Delta

## RENAMED Requirements

- FROM: `### Requirement: A closed issue holds no Status label`
- TO: `### Requirement: A closed issue holds no Status and no Owner label`

## MODIFIED Requirements

### Requirement: A closed issue holds no Status and no Owner label
The workflow `.github/workflows/clear-status.yml` SHALL remove every `status/*` label and every `owner/*` label of an issue when the issue closes, and SHALL remove no other label.

#### Scenario: A merge closes an issue
- **WHEN** an issue that holds `status/in-review`, `owner/agent` and `type/bug` closes
- **THEN** the workflow removes `status/in-review` and `owner/agent` and keeps `type/bug`

## ADDED Requirements

### Requirement: One label family holds the owner of an Item
The roadmap store SHALL read an Item's Owner from the family `owner/service`, `owner/agent` and `owner/human`, and SHALL write it with the rules of the other fields: a job replaces the family, the record names the value the job set, and a write raises `RoadmapItemChangedError` when someone changed the owner since the store read it. An Item with no label of the family SHALL have no owner. `.github/labels.yml` SHALL declare the label of every value of every field.

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
- **WHEN** a test reads `.github/labels.yml`
- **THEN** it declares `owner/service`, `owner/agent`, `owner/human` and the label of every value of Status, Priority, Value and Effort
