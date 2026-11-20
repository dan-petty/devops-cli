## ADDED Requirements

### Requirement: A failed check logs its answered searches and its returns
The alternatives job SHALL keep in each failure of an agent run the number of searches that a provider answered before the failure, and the number of times that the run sent a refused reply back to the model. It SHALL write the two numbers in the `searches` and `returns` fields of the result line of the failure. A search that no provider answered and a refused query SHALL NOT count. A skip-class failure SHALL log 0 for both.

#### Scenario: A refused reply after two answered searches
- **WHEN** the job refuses a reply for reason `url` after the run made two answered searches
- **THEN** the failure holds the count 2, and the result line holds `result=refused`, `reason=url` and `searches=2`

#### Scenario: One answered and one unanswered search
- **WHEN** no provider answers the first search of a run, a provider answers the second, and the job refuses the reply
- **THEN** the result line holds `searches=1`

#### Scenario: A run that stopped after a search
- **WHEN** the run makes one answered search and then stops at its usage limit
- **THEN** the result line holds `result=refused`, `reason=timeout` and `searches=1`

#### Scenario: Each other failure after a search
- **WHEN** the run makes one answered search, and then its model call fails, the item body holds an unpaired marker, or the read of the tools in use fails
- **THEN** the result line holds `searches=1`

#### Scenario: A refusal after a return
- **WHEN** the job sends a `not-applicable` reply back to the model, and then refuses the next reply for reason `url`
- **THEN** the result line holds `result=refused`, `reason=url` and `returns=1`

### Requirement: A url refusal logs each refused URL
When the alternatives job refuses a reply for reason `url`, it SHALL log one WARNING for each source URL of the reply that no tool of the run returned, with the item number, the reason code `url` and the URL. It SHALL log no such line for a source that a tool returned, or for a refusal for another reason.

#### Scenario: A reply cites two URLs that no tool returned
- **WHEN** a reply of item #1 cites a search result, `https://example.com/tool` and `https://example.com/other`, and no tool returned the last two
- **THEN** the log holds two WARNING lines with `#1` and `url`, one for each of the two URLs, and no line names the search result

#### Scenario: A tool with no facts
- **WHEN** the job refuses a `covers` reply for reason `no_facts`
- **THEN** the log holds no WARNING line for reason `url`
