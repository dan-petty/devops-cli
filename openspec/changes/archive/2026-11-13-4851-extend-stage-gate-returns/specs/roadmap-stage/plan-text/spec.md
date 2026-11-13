## MODIFIED Requirements

### Requirement: The stage job checks the form of the plan title
The stage job SHALL run `title_problems` on the title that it builds for the plan. A reply whose title has a problem SHALL go back to the model with the problems, `roadmap.stage.gate_returns` times at most and one more time when the item gets its extra return (`roadmap-stage/returns`, #4851), and a reply with a problem after the last return SHALL stop the item.

#### Scenario: A summary that repeats plan
- **WHEN** the first reply has the summary `plan the form of a task`
- **THEN** the job sends the problem that names the word `plan` to the model, and the second reply sets the title

#### Scenario: A summary with the issue number
- **WHEN** the reply has the summary `Stop #1 dropping a comment` for issue 1, and each returned reply is the same
- **THEN** the job sends a problem that names `#1`, and the item makes no plan
