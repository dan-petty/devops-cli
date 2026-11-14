## ADDED Requirements

### Requirement: A quote of the requirement text opens a finding
A finding of the review SHALL stay open when its quote, with white space folded, is in the requirement text that the request holds, and SHALL be advice when its quote is in none of the texts of the request.

#### Scenario: A finding that quotes a stated requirement
- **WHEN** A review finding quotes the text of a requirement that the stage context selected.
- **THEN** The finding is open and returns the plan, and the test asserts it.

#### Scenario: A finding that quotes a requirement outside the bound
- **WHEN** A review finding quotes a requirement that the stage context does not hold.
- **THEN** The finding is advice, and the test asserts it.

## MODIFIED Requirements

### Requirement: The first review of a plan sends the bounded requirement text
The first review of a plan SHALL get no `earlier` and no `answer` key, the reply schema with only `findings`, and the prompt of the pass with no text of a later review. Its request SHALL hold the bounded requirement text of the stage context in `requirements`. So the golden set of the verify eval, which scores a first review, keeps its request.

#### Scenario: The first review sends its request
- **WHEN** the first review of a plan sends its request
- **THEN** the request holds only `number`, `title`, `body`, `plan`, `files` and `requirements`, and the instructions are the prompt of the pass and the rules of the tools

#### Scenario: The first review does not change
- **WHEN** the first review of a plan sends its request
- **THEN** the request holds only `number`, `title`, `body`, `plan` and `files`, and the instructions are the prompt of the pass and the rules of the tools

## RENAMED Requirements

- FROM: `### Requirement: The first review of a plan keeps its request`
- TO: `### Requirement: The first review of a plan sends the bounded requirement text`
