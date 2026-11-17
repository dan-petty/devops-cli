## Purpose
The ask-mode tools of the roadmap jobs: the research index of fetched page text keyed by the question, the freshness rule of expiry and hash, the store-first lookup, the query refusal, the grep over the stored text, the per-run call limit and the measure of the candidate.

## ADDED Requirements

### Requirement: A fresh answer makes no web call
`research_lookup` SHALL answer from a stored record whose expiry is in the future and whose hash matches the question and the stored page text, and MUST make no web request.

#### Scenario: A fresh record answers the lookup
- **WHEN** the store holds a fresh record for the question
- **THEN** `research_lookup` returns the stored text and the run makes zero `web_search` calls

### Requirement: An expired answer refreshes once
`research_lookup` MUST make one `web_search` call and one page fetch, and update the stored record, when the record is expired or its hash does not match the question and the stored page text.

#### Scenario: An expired record causes one web call
- **WHEN** the store holds a record for the question with an expiry in the past
- **THEN** the run makes one `web_search` call and one page fetch, and the store holds the new text, date, hash and expiry

### Requirement: A query is refused before any request
The ask-mode tools MUST refuse a query that holds a secret pattern, a private address or an e-mail address before any request leaves the process.

#### Scenario: A query with a private address
- **WHEN** the short term of the query holds an RFC 1918 address
- **THEN** `research_lookup` answers with the refusal of the guard of `web_search` and the run sends no HTTP request

### Requirement: The index holds pages, not search results
`ResearchIndex` SHALL write the text of the fetched page, the URL of the fetch and the fetch date with the question, the hash and the expiry, and MUST write no field of a search result.

#### Scenario: A new answer writes page fields only
- **WHEN** the run fetches a page and stores the answer
- **THEN** the row holds the page text, the fetch URL and the fetch date, and holds no title, snippet, rank or age

### Requirement: research_grep matches exact text and a pattern
`research_grep` SHALL match an exact term and a regular expression over the stored page text, and MUST return each match with its URL.

#### Scenario: A regular expression over stored text
- **WHEN** the store holds two pages and the pattern matches one
- **THEN** `research_grep` returns the one matching record with its URL

### Requirement: The tools register through the toolset path
The ask-mode tools SHALL register through the toolset path that refine's investigation, the alternatives check and the stage planner already build, and MUST be offered through no other path.

#### Scenario: The refine, alternatives and stage toolsets hold the new tools
- **WHEN** refine's round and the alternatives check build their tools with a page fetch, and the stage planner runs the `extended` toolset
- **THEN** each toolset holds `research_lookup` and `research_grep`, a refine or alternatives run with no page fetch holds neither, and the stage tools answer that the index is off when `crawl4ai.url` is unset

### Requirement: The per-run limit is a setting
The ask-mode tools MUST stop after the number of calls that the setting `roadmap.research.max_calls_per_run` names, and the setting SHALL have a default.

#### Scenario: The limit stops a run
- **WHEN** a run makes one more ask-mode call than the setting allows
- **THEN** the tool answers that the limit is reached and makes no further request

### Requirement: The measure reports the hit rate and the cost per question
`measure_research` SHALL run the candidate and the chain's web search with no index over the recorded questions, and SHALL report the hit rate and the cost per question of each.

#### Scenario: The measure runs on the recorded questions
- **WHEN** the measure runs on the 10 questions that `recorded_questions` reads from the alternatives and refine comments of the last 30 days
- **THEN** `ResearchMeasure` holds the hit rate and the cost per question of the candidate and of the chain's web search, and `recorded_questions` answers at most 10 questions
