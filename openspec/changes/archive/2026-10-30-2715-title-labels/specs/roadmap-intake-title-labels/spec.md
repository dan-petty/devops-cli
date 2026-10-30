## Purpose
How `devops roadmap intake` gives an item its `type/*` label and its `scope/*` label: from the Conventional Commit title of the issue, with the model picking a type only for a title that has none.

## ADDED Requirements

### Requirement: The title gives the type label
Intake SHALL give an item the `type/*` label that the Conventional Commit type of its title names, and SHALL NOT use the type that the model proposes for such a title. The types `feat` and `fix` SHALL give `type/feature` and `type/bug`, and `perf`, `build` and `ci` SHALL give `type/infra`.

#### Scenario: A fix with a model that proposes another type
- **WHEN** intake places the issue `fix(security): redact a URL user name` and the model proposes `type/security`
- **THEN** the issue gets `type/bug`

#### Scenario: A performance title
- **WHEN** intake places the issue `perf(ci): shorten the Tests check`
- **THEN** the issue gets `type/infra`

### Requirement: The model picks the type of a title with no Conventional Commit type
For a title with no Conventional Commit type, intake SHALL give the item the type that the model proposes, checked against the `type/*` labels of `.github/labels.yml`.

#### Scenario: A plain title
- **WHEN** intake places the issue `The board is slow` and the model proposes `type/bug`
- **THEN** the issue gets `type/bug` and no scope label

### Requirement: The title gives the scope label
Intake SHALL give an item the label `scope/<scope>` when its title has the scope `<scope>` and `.github/labels.yml` declares the label.

#### Scenario: A declared scope
- **WHEN** intake places the issue `fix(security): redact a URL user name`
- **THEN** the issue gets `type/bug` and `scope/security`

### Requirement: A scope with no declared label gets no label and a finding
When the file `.github/labels.yml` does not declare `scope/<scope>`, intake SHALL add no scope label, and the reason comment SHALL name the label and the file.

#### Scenario: An undeclared scope
- **WHEN** intake places the issue `fix(zzz-unknown): a scope that has no label`
- **THEN** the issue gets `type/bug` and no scope label, and the reason comment names `scope/zzz-unknown` and `.github/labels.yml`

### Requirement: A label a person set stays
Intake SHALL keep a `type/*` or `scope/*` label that the issue holds, and SHALL add no label of that family.

#### Scenario: An issue with both labels
- **WHEN** intake places the issue `fix(security): redact a URL` that holds `type/docs` and `scope/ai`
- **THEN** the issue holds `type/docs` and `scope/ai` and no other type or scope label
