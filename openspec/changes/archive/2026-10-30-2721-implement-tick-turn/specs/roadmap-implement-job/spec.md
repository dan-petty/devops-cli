# Spec Delta

## ADDED Requirements

### Requirement: The stop comment of a step holds the diff of the discarded work
When a step stops the item, the comment of the job SHALL also hold the masked diff of the work that the step discarded, in one fenced block, with a note when the diff was cut. The fence SHALL be longer than the longest run of backticks in the diff, and at least three backticks. A stop that is not a step SHALL post no diff.

#### Scenario: A step stops and leaves a diff
- **WHEN** the step of group 1 reports stopped with a diff that holds a token in the form of a GitHub token and a line of three backticks
- **THEN** the comment holds the diff in one fenced block, the fence is four backticks long, the block ends only at the closing fence, the comment holds no token, and the text of the comment after the block is the text of the job

#### Scenario: A cut diff
- **WHEN** the diff of the step was cut
- **THEN** the comment says that the diff is cut to `CONST_ROADMAP_IMPLEMENT_DIFF_CHARS` characters

#### Scenario: A stop that is not a step
- **WHEN** the rebase stops the item
- **THEN** the comment holds no diff

### Requirement: The stop comment cuts a long reason
The job SHALL cut the reason of a stop to `CONST_ROADMAP_IMPLEMENT_REASON_CHARS` characters after it masks secrets in it, so that the stop comment stays below the limit of GitHub.

#### Scenario: A reason that is too long
- **WHEN** a step stops with a reason longer than `CONST_ROADMAP_IMPLEMENT_REASON_CHARS` characters
- **THEN** the comment holds the first `CONST_ROADMAP_IMPLEMENT_REASON_CHARS` characters of the reason
