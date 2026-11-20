## ADDED Requirements

### Requirement: The filed body names its source under its own heading
Intake SHALL file the source of a candidate as the line `Source: <source>` under a `## Source` heading after the body of the candidate. It SHALL write no source line inside a Dependencies section of level 2 or lower, and the source line SHALL name no blocker inside a level-1 Dependencies section, so that the source names no dependency. A retry of a new candidate SHALL find an issue whose body has the form from before this rule, which ends with the line `Source: <source>` and no heading.

#### Scenario: A filed candidate with a source
- **WHEN** `NewCandidate.filed_body` builds the body of a candidate whose body ends with a level-1 `# Dependencies` section and whose source is `#4989`
- **THEN** the body ends with the `## Source` heading and the line `Source: #4989`, and `body_dependencies` of that body returns an empty list

#### Scenario: A retry finds an issue of the old form
- **WHEN** a run before this rule filed a candidate with a source, with the body that ends with the line `Source: <source>`, and stopped before Priority, and intake runs again for the same candidate
- **THEN** intake finds that issue and files no second issue
