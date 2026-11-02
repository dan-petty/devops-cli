## MODIFIED Requirements

### Requirement: The title has a type, a declared scope and a short summary
A title SHALL have the form `<type>(<scope>): <summary>` or `<type>: <summary>`. The type SHALL be one of the types of the project. The scope, when there is one, SHALL be a scope whose `scope/<scope>` label `.github/labels.yml` declares, or `main`. The title SHALL have no `!`. The summary SHALL have at most 60 UTF-16 code units, as the check `Semantic PR title` counts them (an emoji is two), SHALL NOT end with `...` or `…`, and SHALL NOT be a placeholder such as `x` or `placeholder`.

#### Scenario: A title in the form
- **WHEN** the title is `feat(pr): check the form of a pull request` and the labels declare `scope/pr`
- **THEN** the rules find no problem

#### Scenario: A summary of 61 characters
- **WHEN** the summary of the title has 61 characters
- **THEN** the rules find one problem, and its text names the limit 60

#### Scenario: A scope with no label
- **WHEN** the title is `feat(zzz-unknown): build it` and the labels do not declare `scope/zzz-unknown`
- **THEN** the rules find one problem, and its text names `scope/zzz-unknown` and `.github/labels.yml`

#### Scenario: A cut summary
- **WHEN** the summary ends with `...`
- **THEN** the rules find one problem, and its text says that a cut summary reads as broken

#### Scenario: A placeholder summary
- **WHEN** the title is `feat(pr): x`
- **THEN** the rules find one problem, and its text says that the summary is a placeholder

#### Scenario: A mark of a breaking change
- **WHEN** the title is `feat(pr)!: build it`
- **THEN** the rules find one problem, and its text says that nothing is a breaking change before 1.0.0

#### Scenario: No scope check without the labels
- **WHEN** the rules check `feat(zzz-unknown): build it` and are given no label names
- **THEN** the rules find no problem

#### Scenario: An emoji counts as two
- **WHEN** the summary of the title is 31 emoji, which are 31 characters and 62 UTF-16 code units
- **THEN** the rules find one problem, and its text names the length 62 and the limit 60
