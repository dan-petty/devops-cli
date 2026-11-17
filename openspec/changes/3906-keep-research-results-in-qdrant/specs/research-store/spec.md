## Purpose
Keeps the text of each fetched web page in the devops_research Qdrant collection, so a later research round finds the page again without a new search, an expired page goes, and a page with an injection pattern never reaches the agent.

## ADDED Requirements

### Requirement: Research payload
The devops_research collection SHALL store the ADR payload fields on every point: kind, component, source_id, source_url, source_license, fetched_at, expires_at, content_hash, question, severity, exploited, text, untrusted, injection_flag and reported_issue.

#### Scenario: A fetched page is upserted
- **WHEN** A record of a fetched page of the project is upserted with its URL, date, license and expiry
- **THEN** the stored point holds kind, component, source_id, source_url, source_license, fetched_at, expires_at, content_hash, question, severity, exploited, text, untrusted, injection_flag and reported_issue

### Requirement: Equal hash writes once
Upsert SHALL write no point when a point with the same source_id, version and content_hash exists.

#### Scenario: The same record is upserted twice
- **WHEN** Upsert runs twice with the same source_id, version and text
- **THEN** the collection holds one point and the second call returns false

### Requirement: Changed hash updates the point
Upsert SHALL replace the existing point when the content_hash of the same source_id and version changes.

#### Scenario: The text of a fetched page changes
- **WHEN** Upsert runs again with the same source_id and version and a different text
- **THEN** the point keeps its id and holds the new text, content_hash and fetched_at

### Requirement: Expire sweep
Expire SHALL delete every point whose expires_at is earlier than the sweep time.

#### Scenario: One expired point and one live point
- **WHEN** Expire runs at a time after the expires_at of the first of two stored points
- **THEN** the expired point is deleted and the live point stays

### Requirement: Lookup by kind and component
Lookup SHALL filter points by kind and component, run a vector search and return source_url and fetched_at with each hit.

#### Scenario: A query for one kind and component
- **WHEN** Lookup runs with a kind and a component that match one stored point
- **THEN** the result holds that point with its source_url and fetched_at and holds no point of another kind or component

### Requirement: Refuse a record with no provenance
Upsert SHALL refuse a record that has no source_url or no fetched_at, and the error MUST name the missing field.

#### Scenario: A record without a source URL
- **WHEN** Upsert receives a record with no source_url
- **THEN** upsert raises an error that names source_url and writes no point

### Requirement: Refuse a search-result field
Upsert SHALL refuse a record that carries a search-result field (title, snippet, description, rank or provider hit), and the error MUST name the field.

#### Scenario: A record with a title
- **WHEN** Upsert receives a record with a title field
- **THEN** upsert raises an error that names title and writes no point

### Requirement: Refuse text with no fetch
Upsert SHALL refuse a record whose text did not come from a fetch of the project, and the error MUST name the missing fetch.

#### Scenario: A record built from a search hit
- **WHEN** Upsert receives a record built from a search hit, with a text and no fetched page
- **THEN** upsert raises an error that names the missing fetch and writes no point

### Requirement: Injection flag
The store SHALL set injection_flag to true on text that holds an injection pattern and MUST leave that point out of a lookup for the agent.

#### Scenario: A fetched page holds an injection pattern
- **WHEN** The page is upserted and a lookup for the agent runs with matching filters
- **THEN** the stored point has injection_flag true and the lookup result holds no such point

### Requirement: Status shows the collection
The `devops ai rag status` command SHALL list the `devops_research` collection with its point count.

#### Scenario: Status runs against a Qdrant that holds the collection
- **WHEN** `devops ai rag status` runs against a Qdrant that holds the `devops_research` collection
- **THEN** the output names devops_research and its point count

### Requirement: Qdrant address from settings
The store SHALL read the Qdrant address from the project settings and MUST NOT use a fallback URL.

#### Scenario: The Qdrant address setting is unset
- **WHEN** The store is built from settings that hold no Qdrant address
- **THEN** it raises an error that names qdrant.url and sends no request to a default address
