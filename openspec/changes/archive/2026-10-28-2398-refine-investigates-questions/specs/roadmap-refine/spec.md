## ADDED Requirements

### Requirement: Refine investigates a question that has no verified source
When a validated proposal has a fact or a decision with no verified source, or a body key question that no answer names, refine SHALL run one investigation for the item with read-only tools on the pinned commit, and with Firecrawl web search for a public repository with a Firecrawl key. Refine SHALL validate the proposal that the investigation returns as it validates the first. When nothing is open, refine SHALL make no investigation request.

#### Scenario: A fact that a file read settles
- **WHEN** the first proposal answers "Where is the sample function?" as a fact with no source, and the investigation reads `src/sample.py` and answers with the source `src/sample.py:1`
- **THEN** the item has no open question, and refine sets it to Ready

#### Scenario: A fact that a web search settles
- **WHEN** the repository is public, a Firecrawl key is set, the investigation's web search returns `https://example.com/gitleaks`, and the investigation answers the fact with that URL as its source
- **THEN** the item has no open question, and refine sets it to Ready

#### Scenario: A proposal with nothing open
- **WHEN** the first proposal has no open question
- **THEN** refine makes one model request for the item and runs no investigation

### Requirement: A stopped investigation keeps the first proposal
When the investigation stops with no proposal, refine SHALL keep the first proposal, and SHALL NOT report the item as failed.

#### Scenario: The investigation stops with no proposal
- **WHEN** the investigation asks for more tool calls than its budget holds, or its model never answers through the output tool
- **THEN** refine keeps the first proposal, the item waits on a person with its open questions, and the item is not a failed item

### Requirement: A decision names its options and the practice it follows
A decision SHALL list the options it compared, each with the reason it was chosen or rejected, and the refined section SHALL show them. A decision whose answer quotes an owner decision of the body SHALL show "(owner decision)", one with a verified source SHALL show "(best practice)", and one with none SHALL show "(proposed)". An answer SHALL end with only the mark it earns. No decision SHALL make the item wait on a person.

#### Scenario: A sourced decision
- **WHEN** a decision chooses "Use the library" over "Write a parser", cites `src/sample.py`, and gives a reason for each option
- **THEN** the section shows the answer with "(best practice)", the chosen option and the rejected option with their reasons, and the item can be Ready

#### Scenario: A mark copied from an earlier section
- **WHEN** a decision with the verified source `src/sample.py` answers "Use the library. (proposed)"
- **THEN** its answer is "Use the library. (best practice)"

### Requirement: Only a person's decision or an unsourced fact waits on a person
A question of kind `person` SHALL be an open question with "(a person decides)", and the item SHALL wait on a person.

#### Scenario: A decision that AGENTS.md reserves for a person
- **WHEN** the proposal asks "Which repository secret holds the key?" as a `person` question
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

### Requirement: The plan says when web search is off
When refine had no web search in a round, the plan SHALL say so once, with the reason: the repository is private, or no Firecrawl key is set.

#### Scenario: No Firecrawl key
- **WHEN** refine plans a round on a public repository with no Firecrawl key
- **THEN** the report says that web search is off because no Firecrawl key is set
