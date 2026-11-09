## ADDED Requirements

### Requirement: A kept plan holds the trace facts of its run
The plan file SHALL hold the facts of the plan runs that made the plan: the names of the tools that they called, and the paths that they read and that the Feasibility section of the plan cites. A kept plan SHALL be gated with these facts, joined with the facts of each later plan run of the item, so the trace gate neither skips a kept plan nor refuses a claim that the first run supported.

#### Scenario: A revision of a kept plan
- **WHEN** the plan file of an item holds a Feasibility sentence that names `read_issue` and facts with `read_issue`, another gate refuses the kept plan, and the planner revises it with a run that calls no tool
- **THEN** the trace gate accepts the revision

#### Scenario: A claim that the facts lack
- **WHEN** the plan file holds a Feasibility sentence that names `read_issue` and facts without it
- **THEN** the trace gate refuses the kept plan

#### Scenario: The facts are bounded
- **WHEN** the plan runs read many paths and the Feasibility section cites one of them
- **THEN** the plan file holds that path and no other

#### Scenario: A new planner model
- **WHEN** the model of the task `stage` changes
- **THEN** the key is a new value and the kept plan is a miss

### Requirement: A kept plan without facts is planned again
A plan file that holds the current key and no trace facts (the format of an older job) SHALL load, and the planner SHALL count it as a miss, delete it and ask the planner model for a new plan.

#### Scenario: A file in the old format
- **WHEN** the plan file of an item holds the current key, a plan and a request, and no facts
- **THEN** the planner sends the model a request, writes a new file with facts, and counts one `miss` and one `written`
