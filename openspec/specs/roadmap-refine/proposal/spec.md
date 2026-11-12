# roadmap-refine/proposal Specification

## Purpose
The proposal that refine asks of the model: its decisions and questions, its criteria as OpenSpec requirements, the existing-tool answer, the evidence of a stage return, and the form checks with their retries.

## Requirements

### Requirement: A decision names its options and the practice it follows
A decision SHALL list the options it compared, each with the reason it was chosen or rejected, and the refined section SHALL show them. A decision whose answer quotes an owner decision of the body SHALL show "(owner decision)", one with a verified source SHALL show "(best practice)", and one with none SHALL show "(proposed)". An answer SHALL end with only the mark it earns. No decision SHALL make the item wait on a person.

#### Scenario: A sourced decision
- **WHEN** a decision chooses "Use the library" over "Write a parser", cites `src/sample.py`, and gives a reason for each option
- **THEN** the section shows the answer with "(best practice)", the chosen option and the rejected option with their reasons, and the item can be Ready

#### Scenario: A mark copied from an earlier section
- **WHEN** a decision with the verified source `src/sample.py` answers "Use the library. (proposed)"
- **THEN** its answer is "Use the library. (best practice)"

### Requirement: Only a person's decision waits on a person
A question of kind `person` SHALL be an open question with "(a person decides)", and the item SHALL wait on a person. An open question with no such mark SHALL NOT make an item wait on a person.

#### Scenario: A decision that AGENTS.md reserves for a person
- **WHEN** the proposal asks "Which repository secret holds the key?" as a `person` question and the proposal passes its form check
- **THEN** the item waits on a person, and the comment lists "Which repository secret holds the key? (a person decides)"

### Requirement: The body's answered key questions are not asked again
Refine SHALL read the body's "Key questions" section as CommonMark, up to the next heading of the same or a higher level. Only a top-level list item whose first paragraph holds a question mark SHALL be a question. Text after its last question mark, or a block inside the item after that paragraph, SHALL answer it. Refine SHALL send the other questions numbered, and a number that no answer names SHALL be an open question.

#### Scenario: A body that answers its own questions
- **WHEN** the body's "Key questions" hold "- *Which ADR number?* (proposed) The next free one.", "- *Which files?*" with an indented answer under it, and "- #1336 owns the directory."
- **THEN** refine sends no body question and reports no open question

#### Scenario: A body question that no answer names
- **WHEN** the body's "Key questions" hold "- *Which store holds the record?*" and no answer names number 1
- **THEN** "*Which store holds the record?*" is an open question

#### Scenario: A question that wraps, and a paragraph after the list
- **WHEN** the body's "Key questions" hold "- How should refine handle a body" with "that wraps across lines?" on the next line, then a blank line and the paragraph "Context: the Service writes it hourly."
- **THEN** "How should refine handle a body that wraps across lines?" is the one body question

### Requirement: Refine writes each acceptance criterion as an OpenSpec requirement
The refine reply SHALL give each acceptance criterion as `name`, `requirement`, `scenario`, `when` and `then`, and the proposed design SHALL render it as an OpenSpec requirement block: `### Requirement: <name>`, the requirement text, `#### Scenario: <scenario>`, and the `- **WHEN**` and `- **THEN**` lines.

#### Scenario: A criterion in the proposed design
- **WHEN** refine renders a proposal whose criterion has the name `Token cost`, the requirement `The tuner SHALL read the token cost from the ledger.`, the scenario `The ledger has the backend`, the WHEN `the ledger holds records for the backend` and the THEN `the tuner sends no probe`
- **THEN** the section holds `### Requirement: Token cost`, the requirement line, `#### Scenario: The ledger has the backend`, `- **WHEN** the ledger holds records for the backend` and `- **THEN** the tuner sends no probe`, and no `Criterion` or `Verification:` line

#### Scenario: A criterion with the old keys
- **WHEN** a reply gives a criterion as `description` and `verification`
- **THEN** the reply fails validation

### Requirement: A criterion's requirement says SHALL or MUST
The refine reply SHALL be refused when the `requirement` of a criterion does not contain the word SHALL or MUST, as OpenSpec requires of a requirement's text.

#### Scenario: A requirement without the keyword
- **WHEN** a reply's criterion has the requirement `The tuner reads the ledger.`
- **THEN** the reply fails validation with an error that names SHALL and MUST

### Requirement: Refine answers the existing-tool question
The refine reply SHALL carry `existing_tool`: the open, maintained tool or library that covers the need and what it lacks, or the written cost of building instead. Refine SHALL set an item Ready only when that answer is not empty, and SHALL render it under `### Existing Tool Considered`.

#### Scenario: The answer in the proposed design
- **WHEN** refine renders a proposal whose `existing_tool` is `Renovate covers the pin.`
- **THEN** the section holds a `### Existing Tool Considered` heading followed by that text

#### Scenario: An empty answer
- **WHEN** a proposal meets every other readiness rule and its `existing_tool` is empty
- **THEN** refine does not set the item Ready

#### Scenario: A reply without the key
- **WHEN** a reply has no `existing_tool` key
- **THEN** the reply fails validation

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

### Requirement: The model reads the evidence of a stage return
The request of a proposal call SHALL hold the key `stage_return`: the text of the newest comment of the stage job after refine's last comment on an item with no `stage.branch`, without the marker and cut to `CONST_ROADMAP_REFINE_MAX_REPLY_TOKENS`, or `null` when there is none. The comments of the stage job SHALL stay out of `replies`.

#### Scenario: The request after a return
- **WHEN** the stage job returned an item with the evidence "It returns a fixed text." and refine looks at the item again
- **THEN** `stage_return` holds "It returns a fixed text.", holds no marker, and `replies` is empty

#### Scenario: The request of an item with no return
- **WHEN** refine refines an item that the stage job never returned
- **THEN** `stage_return` is `null`

### Requirement: The model reads the reason of a rejected plan
The comment of a rejected plan SHALL be a comment of the stage job. It SHALL stay out of `replies`, and `stage_return` SHALL hold its reason, without the marker of the stage job and without the marker of a rejected plan. Refine SHALL give the item one new look after the comment, as it does after any other return of the stage job.

#### Scenario: The request after a rejected plan
- **WHEN** the stage job commented the reason of a rejected plan and returned the item to New, and refine looks at the item
- **THEN** `stage_return` holds the reason, holds no marker, and `replies` is empty

### Requirement: The prompts of refine name the reason of a rejected plan
The prompts of the proposal and of the investigation SHALL say that the reason in `stage_return` can be the reason of a person who rejected a plan, and that the item must not become Ready again with the same proposal.

#### Scenario: The prompts name the case
- **WHEN** a test reads the two prompts
- **THEN** each one names `stage_return` and a rejected plan

### Requirement: A form check failure is a job failure that retries
When the proposal fails a form check, refine SHALL write no body, no comment and no Status. It SHALL record the failed check names in `refine.failed_check` and the count of tries in `refine.tries`. While the count is below `CONST_ROADMAP_REFINE_MAX_TRIES`, it SHALL record the next step `retry`, and a later round SHALL refine the item again. The form checks are `problem_statement`, `existing_tool` and `acceptance_criteria`.

#### Scenario: A proposal with no problem statement
- **WHEN** the model returns a proposal whose problem statement is empty, and the item has no earlier try
- **THEN** the item has no person wait, `refine.next_step` is `retry`, `refine.tries` is `1`, `refine.failed_check` is `problem_statement`, and refine wrote no comment

#### Scenario: The next round tries again
- **WHEN** a round follows a failed try and nothing changed in the item
- **THEN** the round selects the item and sends one model request for it

### Requirement: A passing proposal clears the job failure
A proposal that passes the form checks with no job failure SHALL clear `refine.tries`, `refine.failed_check`, `refine.failure` and `refine.judge_findings` from the job record.

#### Scenario: A later proposal passes
- **WHEN** the model returns a whole proposal after a failed try
- **THEN** the item is refined as before, and its record holds no `refine.tries`, `refine.failed_check`, `refine.failure` or `refine.judge_findings`

### Requirement: A job failure at the try limit waits on a body edit
When the count of tries reaches `CONST_ROADMAP_REFINE_MAX_TRIES`, refine SHALL record the next step `failed`, and a round SHALL send no model request for the item until a person edits its body.

#### Scenario: The limit is reached
- **WHEN** a proposal fails the same form check on the third round and the limit is 3
- **THEN** `refine.next_step` is `failed`, `refine.tries` is `3`, and the next round sends no model request for the item

#### Scenario: A body edit
- **WHEN** a person edits the body of an item whose next step is `failed`
- **THEN** the next round selects the item, and its count of tries starts at 1
