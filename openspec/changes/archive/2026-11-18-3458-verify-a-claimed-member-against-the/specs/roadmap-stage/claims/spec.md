## ADDED Requirements

### Requirement: A member claim names a member that the class body defines
`check_proposal` SHALL return the member-claim problem when a design decision, a rejected alternative or a `feasibility` line names a class member in a code span and the class body at the staged commit defines no such member.

#### Scenario: A member the staged class lacks is refused
- **WHEN** A decision names `TaskGroup.kind` and quotes `class TaskGroup:`
- **THEN** `check_proposal` returns the member-claim problem for that decision.

#### Scenario: A member the staged class defines is accepted
- **WHEN** A decision names `TaskGroup.tasks` and quotes `tasks: tuple[GroupTask, ...]`
- **THEN** `check_proposal` returns no member-claim problem for that decision.

### Requirement: The member-claim problem names the class, the member and the plan section
The member-claim problem SHALL come from a `RoadmapMessages` entry that names the class, the member and the plan section, so the planner knows which member the class lacks.

#### Scenario: The problem names the class, the member and the section
- **WHEN** The rule refuses a decision that names `TaskGroup.kind`
- **THEN** The problem holds `TaskGroup`, `kind` and the word `decision`.
