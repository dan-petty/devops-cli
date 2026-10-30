# Spec Delta

## Purpose

How `devops pr create` gives the pull request it opens the `type/*` and `scope/*` labels that its Conventional Commit title gives, with the rule of intake, and what the command does when a label cannot be added to a pull request that exists.

## ADDED Requirements

### Requirement: The title gives the labels of a new pull request
After `devops pr create` opens a pull request, it SHALL add the `type/*` label that the Conventional Commit type of the title names, and the label `scope/<scope>` when the title has the scope `<scope>`, each only when `.github/labels.yml` of the repository on the base branch declares it. It SHALL use the same rule as intake, so `fix` gives `type/bug`. A title with no scope SHALL give only the type label. A title with no Conventional Commit type SHALL give no label.

#### Scenario: A fix with a scope
- **WHEN** `devops pr create --title "fix(ai): a title"` opens pull request 14
- **THEN** pull request 14 holds `type/bug` and `scope/ai` and no other label

#### Scenario: A title with no scope
- **WHEN** `devops pr create --title "docs: a title"` opens a pull request
- **THEN** the pull request holds `type/docs` and no scope label

#### Scenario: A title with no type
- **WHEN** `devops pr create --title "A plain title"` opens a pull request
- **THEN** the pull request gets no label and the command prints no warning

### Requirement: A scope with no declared label gets no label and a warning
When `.github/labels.yml` does not declare `scope/<scope>`, the command SHALL add no scope label, SHALL print a warning that names the label and the file, and SHALL exit 0. It SHALL still add the type label.

#### Scenario: An undeclared scope
- **WHEN** `devops pr create --title "fix(zzz-unknown): a title"` opens a pull request
- **THEN** the pull request holds `type/bug` and no scope label, and the output names `scope/zzz-unknown` and `.github/labels.yml`
- **AND** the exit status is 0

### Requirement: A label that cannot be added is reported and the pull request stays
When the label file cannot be read, or a label cannot be added, after the pull request opened, the command SHALL print an error that names the pull request number, each label that was not added, and the reason, and SHALL exit 1. It SHALL try every label, and SHALL NOT close or delete the pull request. The Status of the item that the pull request closes SHALL still be set.

#### Scenario: One label is refused
- **WHEN** GitHub refuses `type/bug` for pull request 14 and accepts `scope/ai`
- **THEN** the command exits 1 and its error names pull request 14, `type/bug` and the reason
- **AND** pull request 14 holds `scope/ai`, and the command sent no request that closes it

#### Scenario: The label file is missing
- **WHEN** the repository has no `.github/labels.yml`
- **THEN** the command exits 1 and its error names pull request 14, `.github/labels.yml` and the reason

### Requirement: A dry run adds no label
`devops --dry-run pr create` SHALL read no label file and add no label.

#### Scenario: A dry run
- **WHEN** `devops --dry-run pr create --title "fix(ai): a title"` runs
- **THEN** the command opens no roadmap store and sends no label request
