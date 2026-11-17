## ADDED Requirements

### Requirement: A job comment is not a reply

The request SHALL leave out every trusted comment that holds a marker of
`CONST_ROADMAP_JOB_COMMENT_MARKERS`, after the selection of the comments that follow the job's last
comment and before the cap of `CONST_ROADMAP_REFINE_MAX_REPLIES`. A comment of a person SHALL stay.

#### Scenario: An intake reason comment

- **WHEN** an item holds an intake reason comment and one person reply, and the job left no comment
- **THEN** the `replies` of the request hold only the person reply

#### Scenario: A refine comment after a check

- **WHEN** a check runs again after a refine comment
- **THEN** the `replies` of the request do not hold the refine comment

#### Scenario: A person reply after a check

- **WHEN** a person replies after the last alternatives comment
- **THEN** the `replies` of the request hold the person reply
