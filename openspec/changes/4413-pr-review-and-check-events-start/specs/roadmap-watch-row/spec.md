## ADDED Requirements

### Requirement: A scoped watch round reads only the delivered pull requests
`watch_round` SHALL take the pull request numbers of a delivery. With numbers it SHALL read a number over REST only when the store records it as the `stage.pr` of an open item or the watch ledger holds it, SHALL skip the GraphQL listing of the open pull requests, and SHALL send no request for a number that neither source names. With no numbers it SHALL read the open pull requests as the poll round does.

#### Scenario: A scoped round reads the delivered pull request
- **WHEN** the store holds open staged drafts 42 and 43, and `watch_round` is called with the pull numbers (42,)
- **THEN** the round reads pull request 42 and sends no request for pull request 43

#### Scenario: A scoped round for an unknown pull request sends no request
- **WHEN** `watch_round` is called with the pull numbers (99,), and neither the store nor the watch ledger names pull request 99
- **THEN** the round sends no request and returns the empty round result

#### Scenario: A round with no numbers reads the listing
- **WHEN** `watch_round` is called with no pull numbers
- **THEN** it reads the open pull requests with one GraphQL query, as the poll does

## MODIFIED Requirements

### Requirement: Watch reads open roadmap pull requests with one GraphQL query
A round of the `watch` row with no delivered pull request number SHALL query all open roadmap pull requests of a repository using one GraphQL query including `headRefOid`, `isDraft`, `mergeable`, and `statusCheckRollup`. When a GraphQL quota hold is active, it SHALL fall back to REST requests with conditional ETags.

#### Scenario: Open pull requests read via GraphQL
- **WHEN** the watch row executes a round with no delivered pull request number for a repository with open pull requests
- **THEN** it issues one GraphQL request to retrieve open pull request details and check runs
