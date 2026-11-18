# research-store Specification

## Purpose
Keeps the text of each fetched web page in the research Qdrant collection, as ADR 0028 defines it, so a later research round finds the page again without a new search, an expired page goes, and a page with an injection pattern never reaches the agent.

## Requirements

### Requirement: Research payload
The research collection SHALL store, on every point, the six fields of ADR 0028 and no other field: source_url, fetch_date, content_hash, expiry, question and text.

#### Scenario: A fetched page is upserted
- **WHEN** A fetched page and the question that it answers are upserted
- **THEN** the stored point holds source_url, fetch_date, content_hash, expiry, question and text, holds no search-result field, and its expiry is 30 days after its fetch_date

### Requirement: Same hash refreshes the dates
Upsert SHALL update fetch_date and expiry of the point of a URL and write no vector when the content_hash of the page equals the stored content_hash.

#### Scenario: The same page is fetched again
- **WHEN** The same page is upserted twice with the same source_url and text, at two different times
- **THEN** the collection holds one point with the later fetch_date and the later expiry, and the vector of the point is written once

### Requirement: Changed hash replaces the text
Upsert SHALL replace the text, content_hash, fetch_date and expiry of the point of a URL when the content_hash changes, and the point keeps its source_url and its id.

#### Scenario: The text of a fetched page changes
- **WHEN** Upsert runs again with the same source_url and a different text
- **THEN** the point keeps its id and holds the new text, content_hash, fetch_date and expiry

### Requirement: Search reads no expired point
Search SHALL return no point whose expiry is earlier than the time of the search, and SHALL return the source_url and the fetch_date with each hit.

#### Scenario: A search for a stored page
- **WHEN** A search runs for a question that a stored live page answers
- **THEN** the result holds that page with its source_url and fetch_date

#### Scenario: One expired page and one live page
- **WHEN** A search runs at a time after the expiry of the first of two stored pages
- **THEN** the result holds no hit for the first page and holds the second page

### Requirement: Expire sweep
Expire SHALL delete every point whose expiry is earlier than the sweep time.

#### Scenario: One expired point and one live point
- **WHEN** Expire runs at a time after the expiry of the first of two stored points
- **THEN** the expired point is deleted and the live point stays

### Requirement: Refuse text with no fetch
Upsert SHALL refuse a page that is not a PageText of the project fetch, and the error MUST name the field page.

#### Scenario: A search hit in place of a page
- **WHEN** Upsert receives a search hit, with a title and a snippet and no page text
- **THEN** upsert raises a ValidationError that names the field page and writes no point

### Requirement: Refuse a blank source URL
Upsert SHALL refuse a page whose source_url is blank, and the error MUST name the field source_url.

#### Scenario: A page with a blank source URL
- **WHEN** Upsert receives a PageText whose source_url is blank
- **THEN** upsert raises a ValidationError that names the field source_url and writes no point

### Requirement: Injection pattern
Search SHALL leave out a hit whose text gives a finding to the injection scan, so the agent never gets such a page.

#### Scenario: A fetched page holds an injection pattern
- **WHEN** A page whose text holds an injection pattern is upserted and a search matches it
- **THEN** the result holds no hit for that page

### Requirement: Status shows the collection
The `devops ai rag status` command SHALL list the research collection with its point count.

#### Scenario: Status runs against a Qdrant that holds the collection
- **WHEN** `devops ai rag status` runs against a Qdrant that holds the research collection
- **THEN** the output names the research collection and its point count

### Requirement: Qdrant address from settings
The store SHALL read the Qdrant address from the project settings and MUST NOT use a fallback URL.

#### Scenario: The Qdrant address setting is unset
- **WHEN** The store is built from settings that hold no Qdrant address
- **THEN** it raises an error that names qdrant.url and sends no request to a default address
