## Purpose

A roadmap job posts a comment on an item only when the facts change, so a round that finds the same facts, or a rerun after a stop of the Service, does not repeat the comment.

## ADDED Requirements

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
