## ADDED Requirements

### Requirement: A behavior group writes the identifiers that it adds
A `behavior` group of the reply SHALL have an `adds` field that lists the identifiers that the group adds. `group_text` SHALL write the names on one `Adds:` line under the line of the kind and the files, each name in a code span and separated by a comma, and SHALL write no `Adds:` line for a group whose `adds` is empty. A `manifest` group and an `other` group SHALL have no `adds`, and a reply that sets one SHALL fail the schema with the title of the group.

#### Scenario: A behavior group adds a guard
- **WHEN** `group_text` renders a `behavior` group whose `adds` holds `_delivery_title`
- **THEN** the line under the kind and the files holds `_delivery_title` in a code span after `Adds:`

#### Scenario: A group of another kind adds a name
- **WHEN** `_other_problems` judges an `other` group whose `adds` holds `_delivery_title`
- **THEN** the reply fails the schema, and the problem text names the title of the group

### Requirement: The stage prompts ask for the identifiers that a group adds
The stage prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` and the split prompt `src/devops_cli/ai/tasks/roadmap_stage_split.md` SHALL name the `adds` field of a `behavior` group in the list of the keys of a group, and SHALL state that each identifier is a plain name, that the writer renders it on an `Adds:` line in a code span, and that a group of another kind adds none.

#### Scenario: The prompts ask for the Adds line
- **WHEN** a person reads the stage prompt and the split prompt
- **THEN** each names the `adds` field, the `Adds:` line and the code span of each name
