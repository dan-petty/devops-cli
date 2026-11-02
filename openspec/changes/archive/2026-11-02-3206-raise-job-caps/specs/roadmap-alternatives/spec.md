# Spec Delta

## MODIFIED Requirements

### Requirement: The request holds the item and the replies
The request to the model SHALL hold the item's title, its body without the record block and without the job's block, the comments after the job's last comment, or every comment when the job left none, and the budget.

#### Scenario: A request
- **WHEN** an item with a body, a job block and two comments after the job's last comment is checked
- **THEN** the request holds the title, the body without the block, the two comments in `replies`, and the budget of `CONST_ROADMAP_ALTERNATIVES_MAX_SEARCHES` searches and `CONST_ROADMAP_ALTERNATIVES_MAX_FACT_READS` fact reads

## ADDED Requirements

### Requirement: The check reads the context window of the analysis task
The run of one item SHALL pass the context window of the `analysis` task to the investigation, so that the window ends the tools of the run before the counts do.

#### Scenario: The window reaches the run
- **WHEN** an item is checked and the window of the `analysis` task is 65536 tokens
- **THEN** the investigation gets the window 65536
