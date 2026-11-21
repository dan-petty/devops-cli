## ADDED Requirements

### Requirement: The plan refuses repair text in the Feasibility lines
The stage gate SHALL refuse each line of the plan's `feasibility` list that refers to an earlier reply or states a self-correction, and it MUST read no line inside a fenced code block or a block quotation, and no text inside an inline code span.

#### Scenario: Earlier reply phrase
- **WHEN** A Feasibility line holds `The earlier reply was wrong`.
- **THEN** `meta_text_problems` returns one problem with the number of that line and the phrase, so the `meta-text` gate refuses the plan.

#### Scenario: Quoted probe line
- **WHEN** A fenced code block, a block quotation or an inline code span holds the text `The earlier reply was wrong`.
- **THEN** `meta_text_problems` returns no problem for that line, so the `meta-text` gate passes it.

#### Scenario: Two repair phrases
- **WHEN** Two Feasibility lines hold two different repair phrases.
- **THEN** `meta_text_problems` returns two problems, one for each line number and each phrase.

#### Scenario: Objective text
- **WHEN** The Feasibility lines hold a file citation and a quoted probe result with no repair phrase.
- **THEN** `meta_text_problems` returns no problem, so the `meta-text` gate passes the plan.
