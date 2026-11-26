# roadmap-store-issue-read Specification

## Purpose

The comparison that the GitHub roadmap store makes between the answer of a request of an issue by its number and the request, so that the store takes an answer as the issue that it asked for only when the answer names that issue of its repository.

## Requirements

### Requirement: An issue read compares the answer with the request
`GitHubRoadmapStore` SHALL take the answer of a read of an issue or a pull request by its number as that issue only when the `number` of the answer is the requested number and the answer names the repository of the store. For an answer that names another issue, `issue`, `item` and `pull_title` SHALL return None, and `read_issue_body` SHALL raise `GitHubOperationError` with the message `#<number> is not an issue of <repository>.`

#### Scenario: An answer with another number and another repository
- **WHEN** the fake GitHub answers the read of `repos/acme/widgets/issues/7` with a payload whose `number` is 12 and whose `repository_url` names `acme/other`
- **THEN** `issue(7)` and `item(7)` of the store of `acme/widgets` return None, and `read_issue_body(7)` raises `GitHubOperationError` with the message `#7 is not an issue of acme/widgets.`

#### Scenario: An answer with another number of the same repository
- **WHEN** the fake GitHub answers the read of `repos/acme/widgets/issues/7` with a payload whose `number` is 12 and whose `repository_url` names `acme/widgets`
- **THEN** `issue(7)` and `item(7)` return None

#### Scenario: A pull request title read that answers with another pull request
- **WHEN** the fake GitHub answers the read of `repos/acme/widgets/issues/7` with a payload that holds `pull_request`, whose `number` is 12 and whose `repository_url` names `acme/other`
- **THEN** `pull_title(7)` returns None

#### Scenario: An answer for the requested number and repository reads as before
- **WHEN** the fake GitHub answers the read of `repos/acme/widgets/issues/7` with a payload whose `number` is 7 and whose `repository_url` names `acme/widgets`
- **THEN** `issue(7)` returns the record of the payload with the number 7, `item(7)` returns its item, and `read_issue_body(7)` returns its body

### Requirement: The repository of an answer comes from its URL fields
The store SHALL take the repository that an answer names from `repository_url`, else from `url`, else from the page URL `html_url`. The comparison of the names SHALL ignore their case. An answer that names no repository SHALL be compared by its number only.

#### Scenario: Another repository in the URL of the issue or of its page
- **WHEN** the fake GitHub answers the read of `repos/acme/widgets/issues/7` with a payload whose `number` is 7, that holds no `repository_url`, and whose `url` and `html_url`, or whose `html_url` alone, name `acme/other`
- **THEN** `issue(7)` and `item(7)` return None

#### Scenario: The name in another case, in a URL field, or in no field
- **WHEN** the fake GitHub answers the read of `repos/acme/widgets/issues/7` with a payload whose `number` is 7 and that names `Acme/Widgets` in `repository_url`, or names `acme/widgets` only in `url` and `html_url`, or holds the `html_url` `https://example.com/issues/7` and no other URL
- **THEN** `issue(7)` returns the record of the payload with the number 7

### Requirement: A conditional read compares its answer
The store SHALL compare the answer of a conditional read with `If-None-Match` with the request as it compares the answer of a plain read.

#### Scenario: A conditional read that answers with another issue
- **WHEN** the brain entry of issue 7 is older than one hour, and the fake GitHub answers the read with `If-None-Match` with status 200 and a payload whose `number` is 12 and whose `repository_url` names `acme/other`
- **THEN** `issue(7)` returns None

### Requirement: A refused answer logs the requested number
For an answer that names another issue, the store SHALL log a warning that holds the requested number and the name of its own repository. No log line of the store SHALL hold a field of the answer.

#### Scenario: The warning names the requested number only
- **WHEN** a store that read no listing reads issue 7, and the fake GitHub answers the read of `repos/acme/widgets/issues/7` with a payload whose `number` is 12 and whose `repository_url` names `acme/other`
- **THEN** the store logs one warning that holds `#7` and `acme/widgets`, and holds neither `12` nor `acme/other`

### Requirement: A write is refused when its read answers with another issue
A write of `GitHubRoadmapStore` that reads the issue first SHALL raise `GitHubOperationError` with the message `#<number> is not an issue of <repository>.` and SHALL send no write request when that read answers with another issue. These writes are `set_field`, `set_fields`, `set_marks`, `write_issue_body`, `set_title` and `close`, and `add_sub_issue` and `add_blocked_by` when they read the issue.

#### Scenario: A mark write after the issue left the repository
- **WHEN** a store of `acme/widgets` read item 7, the fake GitHub then answers the read of `repos/acme/widgets/issues/7` with a payload whose `number` is 12 and whose `repository_url` names `acme/other`, and the store calls `set_marks` for the item
- **THEN** the call raises `GitHubOperationError` with the message `#7 is not an issue of acme/widgets.`, and the fake GitHub holds no request with `POST`, `PATCH` or `DELETE`

### Requirement: The answer of an issue write is compared with the request
The store SHALL compare the answer of the `PATCH` of an issue with the request as it compares the answer of a read. An answer that names another issue SHALL fail the write with `GitHubOperationError`, and the store SHALL NOT keep it in its listing or in the brain.

#### Scenario: The answer of a write names another issue
- **WHEN** the fake GitHub answers the read of `repos/acme/widgets/issues/7` with issue 7 of `acme/widgets` and its `PATCH` with a payload whose `number` is 12 and whose `repository_url` names `acme/other`, and the store calls `set_title` for issue 7
- **THEN** the call raises `GitHubOperationError` with the message `#7 is not an issue of acme/widgets.`, and the `valkey_server` fake holds no entry of issue 12 of `acme/widgets`

### Requirement: A row sends no write for an item whose read answers with another issue
A round of the alternatives check and a Status sweep SHALL send no write request for an item of the listing whose issue read answers with another issue. The Status sweep SHALL leave the item and go on with the other items. The alternatives round SHALL end with the `GitHubOperationError` of a missing issue. The next round of the same lane SHALL NOT select the item.

#### Scenario: An alternatives round
- **WHEN** the snapshot of a lane holds the open item 7 of `acme/widgets`, whose type is a skip class, the fake GitHub answers the read of issue 7 with issue 12 of `acme/other`, and the lane runs two rounds of the alternatives check
- **THEN** the first round raises `GitHubOperationError` with the message `#7 is not an issue of acme/widgets.`, the second round checks no item, and the fake GitHub holds no request with `POST`, `PATCH` or `DELETE`

#### Scenario: A Status sweep
- **WHEN** the snapshot of a lane holds the open item 7 of `acme/widgets` with the Status Ready that a job recorded, its plan is on the default branch, the fake GitHub answers the read of issue 7 with issue 12 of `acme/other`, and the lane runs two Status sweeps
- **THEN** each sweep writes no item and reports no failure, the store of the second sweep does not list item 7, and the fake GitHub holds no request with `POST`, `PATCH` or `DELETE`
