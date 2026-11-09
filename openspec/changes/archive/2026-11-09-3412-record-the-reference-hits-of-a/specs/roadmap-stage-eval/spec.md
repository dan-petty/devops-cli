# roadmap-stage-eval Delta

## ADDED Requirements

### Requirement: The golden set records the reference hits of a case
The `facts.json` of a stage case SHALL hold a `references` list: the paths of the files that hold the old path or the dotted name of a moved module. A case with no `references` key SHALL read an empty list, so its verdict stays as it is. `PlanUnderTest` SHALL hold the recorded paths, and the `paths` gate SHALL pass them to `check_proposal` as its reference hits.

#### Scenario: Recorded hits reach the plan
- **WHEN** the replay loads a case whose `facts.json` holds two reference paths
- **THEN** `PlanUnderTest.of_case` holds the same two paths in its `references` field

#### Scenario: The check receives the hits
- **WHEN** the replay runs the `paths` gate on a case with two recorded reference paths
- **THEN** `check_proposal` receives the same two paths as its reference hits

#### Scenario: An existing case replays as before
- **WHEN** the replay runs the whole golden set with a case that has no `references` key
- **THEN** that case reads an empty list and the report lists no failure for it

### Requirement: The golden set holds a missed reference hit
The golden set SHALL hold a case that moves a module and leaves a string literal of the old name in `tests/`, with one `missing_path` defect that names the test file and the gate `paths`.

#### Scenario: The replay catches the missed reference
- **WHEN** the replay runs the new case
- **THEN** the `paths` gate refuses the plan and the report marks the defect `caught`
