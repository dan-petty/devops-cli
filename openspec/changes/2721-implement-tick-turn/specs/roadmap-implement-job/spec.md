# Spec Delta

## MODIFIED Requirements

### Requirement: A stopped item goes back to Ready and is never retried
When a step, the rebase, the documentation, the archive, a push or the checks stop the item, the job SHALL post a comment that starts with the marker and names the step, the reason and the last message of the agent, SHALL set Status to Ready, and SHALL record `implement.stopped` with the step. When a step stops, the comment SHALL also hold the masked diff of the work that the step discarded, in one fenced block, with a note when the diff was cut. The fence SHALL be longer than the longest run of backticks in the diff, and at least three backticks. It SHALL push the commits of the steps that passed. The job SHALL NOT run the item again until a retry comment clears the record. The job SHALL go on to the next selected item.

#### Scenario: A step stops
- **WHEN** the step of group 2 reports stopped
- **THEN** Status is Ready, `implement.stopped` is `group 2`, the comment holds the reason, `origin` holds the commit of group 1, and the pull request is still a draft

#### Scenario: A step stops and leaves a diff
- **WHEN** the step of group 1 reports stopped with a diff that holds a token in the form of a GitHub token and a line of three backticks
- **THEN** the comment holds the diff in one fenced block, the fence is four backticks long, the block ends only at the closing fence, the comment holds no token, and the text of the comment after the block is the text of the job

#### Scenario: A stop that is not a step
- **WHEN** the rebase stops the item
- **THEN** the comment holds no diff

#### Scenario: A conflict on the rebase before a push
- **WHEN** the default branch gains a change that conflicts with the branch after the last group, or after the fix step
- **THEN** the job aborts the rebase, `origin` holds the commits that passed, Status is Ready, and `implement.stopped` is `push`
