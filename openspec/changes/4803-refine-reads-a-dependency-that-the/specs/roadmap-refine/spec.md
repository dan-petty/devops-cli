## ADDED Requirements

### Requirement: Refine reads a dependency that the body names by its title
Refine SHALL add to the dependencies of a proposal each issue that the Dependencies section of the body names by a quoted Conventional Commit title: the one open Item with that exact title, else the one closed Item with it. A list item that names `#N` SHALL name its issue by the number. A title that names no Item or two Items SHALL fail the round with the job check `dependencies`, and the error SHALL ask for `#<number>`.

#### Scenario: An open issue named by its title
- **WHEN** the Dependencies section names the quoted title of an open issue and the proposal names no dependency
- **THEN** the item has the next step `blocked` with that issue, and the refine section lists the issue under Dependencies

#### Scenario: A closed issue named by its title
- **WHEN** the Dependencies section names the quoted title of a closed issue
- **THEN** the item reaches Ready, and the refine section lists the issue under Dependencies

#### Scenario: A title that names no single issue
- **WHEN** the Dependencies section names a quoted title that no issue has, or that two open issues have
- **THEN** the item has the next step `retry`, `refine.failed_check` is `dependencies`, `refine.failure` names the title and asks for `#<number>`, and refine wrote no comment

#### Scenario: Quoted text that is no title, and an item with a number
- **WHEN** the Dependencies section holds a quoted tool name, and a list item that names `#N` and a title that no issue has
- **THEN** the round has no job failure
