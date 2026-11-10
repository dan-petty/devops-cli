## ADDED Requirements

### Requirement: A run has a call budget
From call `CONST_ROADMAP_STAGE_PLAN_CALLS_NOTICE` of a stage plan run, and from call `CONST_ROADMAP_STAGE_REVIEW_CALLS_NOTICE` of a review run, the answer of each tool SHALL end with a notice that names the call number and tells the model to read no more and give its reply. The tools SHALL stay on, and each run SHALL start its count at zero.

#### Scenario: A plan run past its budget
- **WHEN** a plan run makes three calls and the budget of a plan run is 2
- **THEN** the answer of the first call has no notice, and the answers of the second and third calls end with the notice

#### Scenario: A review run
- **WHEN** a review run makes three calls, the budget of a plan run is 1 and the budget of a review run is 3
- **THEN** only the answer of the third call ends with the notice

#### Scenario: A new run
- **WHEN** a second run starts after a run that passed its budget
- **THEN** the first answers of the second run have no notice

### Requirement: The prompts of a run name its call budget
The prompt of a stage plan run SHALL say that a plan needs about `CONST_ROADMAP_STAGE_PLAN_CALLS_ADVISED` tool calls, and the prompt of a review run SHALL say that a review needs about `CONST_ROADMAP_STAGE_REVIEW_CALLS_ADVISED`. Each prompt SHALL name the call from which the answers carry the notice. The prompt of a plan run SHALL say that a request with `problem` needs a tool call only to check what the problem names.

#### Scenario: The prompts
- **WHEN** the prompts of the plan run and the review run are read
- **THEN** they name the advised calls and the call of the notice that the constants hold
