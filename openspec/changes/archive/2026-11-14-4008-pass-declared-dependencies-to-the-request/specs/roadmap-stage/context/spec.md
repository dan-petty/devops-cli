## ADDED Requirements

### Requirement: The request lists the declared issue dependencies
The stage request SHALL hold `issue_dependencies` with one entry for each issue that the Dependencies section of the item body names, in the order of the body. An entry SHALL hold `number` and, when the store holds the issue, `title`. The request SHALL omit the key when the body declares no dependency.

#### Scenario: Two declared dependencies
- **WHEN** the body names `#2` and `#3` in its Dependencies section, and the store holds both as items with a title
- **THEN** the request holds `[{"number": 2, "title": "..."}, {"number": 3, "title": "..."}]`

#### Scenario: An issue that the store lacks
- **WHEN** the body names `#99` and the store holds no issue 99
- **THEN** its entry is `{"number": 99}` with no `title` key

#### Scenario: No dependency in the body
- **WHEN** the body has no Dependencies section
- **THEN** the request holds no `issue_dependencies` key

### Requirement: The prompt names the declared dependencies
The prompt `roadmap_stage_change.md` SHALL state that `issue_dependencies` holds each issue of the Dependencies section and that the model writes one `dependencies` entry for each as `#<number>: <reason>`.

#### Scenario: The stage prompt
- **WHEN** a test loads the prompt of the task `stage`
- **THEN** the prompt holds `issue_dependencies` and `#<number>: <reason>`
