## ADDED Requirements

### Requirement: The no-change stop names the group and asks for a smaller one
A group step that changes no file SHALL stop with the failure class `plan_defect`, and its reason SHALL name the number and the title of the group and SHALL ask for a smaller replacement through a plan request of kind `group`.

#### Scenario: A group that changes no file
- **WHEN** a group step ends and the checkout holds no staged change
- **THEN** the outcome is stopped, its `failure_class` is `plan_defect`, and its reason holds the number, the title and the request for a smaller replacement

### Requirement: The trace holds plan_defect for the no-change group only
The attempt event of a group step that changes no file SHALL hold the class `plan_defect`, and the attempt event of a group step that changes a file SHALL hold no class.

#### Scenario: One group changes no file and one changes a file
- **WHEN** the trace records one group step that changes no file and one group step that changes a file
- **THEN** the first attempt event holds `plan_defect`, and the second holds an empty class
