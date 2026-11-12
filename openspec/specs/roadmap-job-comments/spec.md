# roadmap-job-comments Specification

## Purpose
A roadmap job posts a comment on an item only when the facts change, so a round that finds the same facts, or a rerun after a stop of the Service, does not repeat the comment.

## Requirements

### Requirement: A job posts no comment that repeats its own recent comment
A store SHALL refuse a comment that holds a job marker when a comment with the same text, with commits, digests and run IDs left out, is in the trailing run of comments with that marker on the item and is less than 7 days old. It SHALL count the refusal in `devops_cli_roadmap_comment_repeats_refused_total` by the row of the job.

#### Scenario: The same wait at a new commit
- **WHEN** refine posts a wait comment and the next round posts the same text at another commit
- **THEN** the item holds one comment and the counter adds 1 under the row `refine`

#### Scenario: A changed fact
- **WHEN** the second comment names another blocker
- **THEN** both comments post

#### Scenario: A person's reply
- **WHEN** a person replies between the two comments
- **THEN** both comments post

#### Scenario: A stop after each write
- **WHEN** the stage job returns an item to New and the Service stops after its comment or after its Status write
- **THEN** the next round posts no second comment

### Requirement: A refused refine repeat starts the wait at its round
When the store refuses a comment of refine as a repeat, refine SHALL record the time of the round in `refine.repeated_at`. The wait of the item SHALL start at the later of that time and refine's last comment, so a change of a cited path or a named issue before the round SHALL NOT end the wait again.

#### Scenario: One change of a cited path
- **WHEN** a commit changes the cited path of a waiting item, the new look finds the same wait, and two more rounds run
- **THEN** the item holds one refine comment, and the change gave one model call

#### Scenario: A second change
- **WHEN** a second commit changes the cited path after that round
- **THEN** the rounds after it make one more model call
