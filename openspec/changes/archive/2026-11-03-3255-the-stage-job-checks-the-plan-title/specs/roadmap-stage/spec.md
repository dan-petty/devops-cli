## ADDED Requirements

### Requirement: The stage job checks the form of the plan title
The stage job SHALL run `title_problems` on the title that it builds for the plan. A reply whose title has a problem SHALL go back to the model once with the problems, and a second reply with a problem SHALL stop the item.

#### Scenario: A summary that repeats plan
- **WHEN** the first reply has the summary `plan the form of a task`
- **THEN** the job sends the problem that names the word `plan` to the model, and the second reply sets the title

#### Scenario: A summary with the issue number
- **WHEN** the reply has the summary `Stop #1 dropping a comment` for issue 1, and the second reply is the same
- **THEN** the job sends a problem that names `#1`, and the item makes no plan
