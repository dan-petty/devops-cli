## ADDED Requirements

### Requirement: A decision needs a rejected alternative with a fact
The stage check SHALL refuse a proposal that holds at least one decision and no rejected alternative, and SHALL refuse a rejected alternative whose evidence holds no path and line, no quoted command output and no number.

#### Scenario: A decision with no rejected alternative is refused
- **WHEN** A proposal holds one decision and an empty rejected list
- **THEN** The stage check returns a problem that names the decision and the Rejected alternatives part of the design file

#### Scenario: An alternative with a number passes
- **WHEN** A proposal with one decision holds a rejected alternative whose evidence is the number 422 of the page 300 answer
- **THEN** The stage check returns no problem

#### Scenario: An alternative with a quoted output passes
- **WHEN** A proposal with one decision holds a rejected alternative whose evidence is the quoted output no matches
- **THEN** The stage check returns no problem

#### Scenario: An alternative with only an opinion is refused
- **WHEN** A proposal with one decision holds a rejected alternative whose evidence is the sentence This option is worse.
- **THEN** The stage check returns a problem that names that alternative

### Requirement: The planner prompt states the rejected alternative rule
The stage planner prompt SHALL state that a plan with a decision gives at least one rejected alternative under the Rejected alternatives part of the design file, and that its evidence holds a path and line, a quoted command output or a number.

#### Scenario: The prompt and the design rule hold the rule
- **WHEN** A test reads the stage planner prompt and the design rule of the config
- **THEN** Both texts hold the Rejected alternatives part and the rule of one fact
