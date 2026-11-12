# roadmap-refine/investigation Specification

## Purpose
The investigation of an open question of a refine proposal: the read tools and the web search, the context window, and what refine keeps when the investigation stops.

## Requirements

### Requirement: Refine investigates a question that has no verified source
When a validated proposal has a fact or a decision with no verified source, or a body key question that no answer names, refine SHALL run one investigation for the item with read-only tools on the pinned commit, and with web search for a public repository with at least one configured search provider. Refine SHALL validate the proposal that the investigation returns as it validates the first. When nothing is open, refine SHALL make no investigation request.

#### Scenario: A fact that a file read settles
- **WHEN** the first proposal answers "Where is the sample function?" as a fact with no source, and the investigation reads `src/sample.py` and answers with the source `src/sample.py:1`
- **THEN** the item has no open question, and refine sets it to Ready

#### Scenario: A fact that a web search settles
- **WHEN** the repository is public, a search provider is configured, the investigation's web search returns `https://example.com/gitleaks`, and the investigation answers the fact with that URL as its source
- **THEN** the item has no open question, and refine sets it to Ready

#### Scenario: A proposal with nothing open
- **WHEN** the first proposal has no open question
- **THEN** refine makes one model request for the item and runs no investigation

### Requirement: A stopped investigation keeps the first proposal
When the investigation stops with no proposal, refine SHALL keep the first proposal. When a question that is not marked "(a person decides)" is still open, refine SHALL record a job failure with the failed check `investigation_stopped` and the first line of the error, and SHALL NOT keep that question as a wait on a person.

#### Scenario: The investigation stops with no proposal
- **WHEN** the investigation asks for more tool calls than its budget holds, and the first proposal holds only a `(proposed)` decision
- **THEN** refine keeps the first proposal, and the item is not a failed item

#### Scenario: The output retries run out
- **WHEN** the investigation of an item with a `(missing verified source)` question stops with `Exceeded maximum output retries (2)`
- **THEN** the item has the next step `retry`, its job record names the check `investigation_stopped` and holds the error, and no comment lists the question

### Requirement: The investigation reads the context window of the analysis task
The investigation of an item SHALL pass the context window of the `analysis` task to the run, so that the run offers no tool to a request when its messages and a quarter of the window reach the window. The window SHALL end the tools of a run before the counts of requests and tool calls do when the window is small. The run SHALL keep both counts as the loop guard of the job.

#### Scenario: A small window
- **WHEN** the window of the `analysis` task is 6000 tokens and the model calls a tool in every reply
- **THEN** a request offers no tool before the count of requests, and the reply of the model ends the run with its proposal

#### Scenario: A large window
- **WHEN** the window is larger than any run can fill and the model calls a tool in every reply
- **THEN** the count of requests ends the tools, and the last request offers no tool

### Requirement: A source question is answered with the read tools or reports what they searched
When a question has no verified source after the investigation, refine SHALL treat it as a job failure with the failed check `missing_source`, and SHALL record in `refine.failure` the calls of the read tools that the investigation made. The item SHALL NOT wait on a person for it.

#### Scenario: A read tool finds the source
- **WHEN** the first proposal answers "Where is the sample function?" as a fact with no source, and the investigation reads `src/sample.py`
- **THEN** the item has no open question and no job failure

#### Scenario: No tool finds the source
- **WHEN** the investigation searches for a text that the repository does not hold and answers with no source
- **THEN** the item has the next step `retry`, `refine.failed_check` is `missing_source`, and `refine.failure` names the search call and its text

### Requirement: The plan says when web search is off for want of a provider
When refine had no web search in a round, the plan SHALL say so once, with the reason: the repository is private, its visibility could not be read, or no search provider is configured.

#### Scenario: No search provider
- **WHEN** refine plans a round on a public repository whose providers are all unconfigured
- **THEN** the report says that web search is off because no search provider is configured

#### Scenario: The keyless provider
- **WHEN** refine plans a round on a public repository with the default providers and no Firecrawl key
- **THEN** web search is on
