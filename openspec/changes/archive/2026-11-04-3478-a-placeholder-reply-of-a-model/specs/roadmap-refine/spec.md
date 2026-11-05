## ADDED Requirements

### Requirement: The refine reply holds no placeholder text
`RefinementProposal` SHALL use `ReplyText` for `problem_statement`, `existing_tool` and each free-text field of its acceptance criteria, key questions, options and deferred parts, and for each line of `split_offs`. `suspected_block` SHALL stay a plain text, because `none` is a valid value of it.

#### Scenario: x in both required keys
- **WHEN** a reply sets `problem_statement` and `existing_tool` to `x` and gives no acceptance criterion
- **THEN** the schema refuses the reply with two violations of the type `placeholder_text`

#### Scenario: A refusal of the task
- **WHEN** a reply sets `existing_tool` to "Not yet: I need to inspect the repository first."
- **THEN** the schema refuses the reply

#### Scenario: A real answer
- **WHEN** a reply sets `problem_statement` to a sentence and `existing_tool` to "Pydantic covers the schema check."
- **THEN** the schema accepts the reply

#### Scenario: No block
- **WHEN** a reply sets `suspected_block` to `none`
- **THEN** the schema accepts the reply

### Requirement: A placeholder reply is retried once and then fails
Refine SHALL ask the model for the proposal with one retry. A reply that holds a placeholder SHALL go back to the model with the schema report once. A second reply with a placeholder SHALL be a placeholder failure of the item: refine SHALL write the warning of a failed call, SHALL write no mark, no comment and no body for the item, SHALL ask no person and SHALL set no Status. The failure SHALL stay in `failed_items` of the plan.

#### Scenario: The retry answers well
- **WHEN** the first reply holds `x` as the problem statement and the second reply is valid
- **THEN** refine uses the second reply, and the model got two calls

#### Scenario: Two placeholder replies
- **WHEN** both replies hold `x` as the problem statement
- **THEN** the item gets no comment, no body change, no mark and no Status change, and `failed_items` names it

#### Scenario: A placeholder with another violation
- **WHEN** the last reply holds `x` as the problem statement and breaks another rule of the schema
- **THEN** the failure is a normal schema failure of the item

### Requirement: A placeholder failure does not fail the round
`raise_for_failed_items` SHALL NOT count a placeholder failure. A round whose only failures are placeholder failures SHALL succeed, so `FailureLedger` counts no failed round and does not suspend the refine row.

#### Scenario: Only a placeholder failure
- **WHEN** one item of a round fails with a placeholder failure and the others are refined
- **THEN** the round raises no error, and a ledger that ran it three times in a row does not suspend the row

#### Scenario: A placeholder failure and another failure
- **WHEN** one item fails with a placeholder failure and another fails with a timeout
- **THEN** the round raises an error that names the timeout item only
