## ADDED Requirements

### Requirement: Only an answered search counts as a search
A search SHALL count as a search of the check only when a search provider answered it, with results or with no result. A search that no provider answered, and a query that the guard refused, SHALL NOT count. Every call of `search_web` SHALL count toward the limit `CONST_ROADMAP_ALTERNATIVES_MAX_SEARCHES`, whether it was answered or not. The text that the tool answers to the model SHALL not change.

#### Scenario: Every search fails
- **WHEN** no provider answers, and the model searches once and then gives the verdict `none` twice
- **THEN** the item is skipped with the reason that the reply gives a verdict with no answered search, its job record names the class `RefusedReply`, and nothing is written to its body or its comments

#### Scenario: A search fails and a later search is answered
- **WHEN** the first search of a run fails, the model searches again, a provider answers, and the model gives the verdict `none`
- **THEN** the check is written, and it lists the one answered search

#### Scenario: A search that answered with no result
- **WHEN** a provider answers a search with no result and the model gives the verdict `none`
- **THEN** the check is written, and it lists the query with `results: 0`

#### Scenario: Failed searches use the limit
- **WHEN** no provider answers and the model calls `search_web` one time more than the limit
- **THEN** the tool sends one request for each call up to the limit, answers the last call that the limit is reached, and records no search

## MODIFIED Requirements

### Requirement: The comment lists the searches and the tools considered
The comment SHALL list every tool whose facts the run read with its URL, license and last activity, and each search that a provider answered with its number of results.

#### Scenario: Two searches with results
- **WHEN** a run makes two searches and the fake search returns two results each
- **THEN** the comment lists each query with `results: 2`

#### Scenario: Two tools read
- **WHEN** the run reads the facts of two repositories and names one as the tool
- **THEN** the comment lists both under `Tools considered:`, each with its license and last activity

### Requirement: A non-skip item needs a search before any verdict
For an item that is no skip class, the check SHALL refuse a reply that follows no answered `search_web` call, and SHALL give the model one more turn to search. A second reply that follows no answered search SHALL end as a failed check: the job skips the item with a named reason and writes nothing for it. The check SHALL refuse a reply with the verdict `not-applicable` from the model, because the job sets that verdict for a skip class only.

#### Scenario: A reply with no search gets one more turn
- **WHEN** the model answers a `feat` item with the verdict `none` and no search, then searches, then answers with the verdict `none`
- **THEN** the model received three requests, the check is written with the query of the search, and the counter `devops_cli_web_searches_total` has a point

#### Scenario: Two replies with no search
- **WHEN** the model answers a `feat` item twice with a verdict and no search
- **THEN** the model received two requests, the item is skipped with the reason that the reply gives a verdict with no answered search, and nothing is written for it

#### Scenario: A not-applicable reply from the model
- **WHEN** the model searches for a `feat` item and then answers with the verdict `not-applicable`
- **THEN** the item is skipped with the reason that the job sets `not-applicable` for a skip class only, and nothing is written for it

### Requirement: Each written check observes its searches
For each check that it writes, the job SHALL observe the histogram `devops_cli_roadmap_alternatives_searches` once, with the attribute `verdict` and the number of searches that a provider answered for the check. A skip-class check SHALL observe 0. The job SHALL observe nothing for a failed check, for a check skipped because a person changed the body, and for a plan that it does not apply.

#### Scenario: A check that searched three times
- **WHEN** the job writes a check with the verdict `none` after 3 answered searches
- **THEN** the histogram has the point `{verdict="none"}` with the value 3

#### Scenario: A skip-class check
- **WHEN** the job writes the check of an item titled `docs(roadmap): a change`
- **THEN** the histogram has the point `{verdict="not-applicable"}` with the value 0

#### Scenario: A check that is not written
- **WHEN** a check fails, a person changes the body between the read and the write, or a run only plans
- **THEN** the histogram has no point for that item
