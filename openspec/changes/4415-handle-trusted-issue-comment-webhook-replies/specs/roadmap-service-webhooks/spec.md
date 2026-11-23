## ADDED Requirements

### Requirement: The payload holds the comment and the pull request marker
`GitHubWebhookPayload` SHALL parse an optional `comment` that holds `body`, `author_association` and `created_at`, and `WebhookIssue` SHALL parse an optional `pull_request` marker. A payload that holds neither SHALL validate as it did before.

#### Scenario: An issue comment payload
- **WHEN** a test validates an `issue_comment` payload that holds a comment and an `issue.pull_request` marker
- **THEN** the payload holds the comment body, its author association and its time, and the issue holds the pull request marker

#### Scenario: A payload with no comment
- **WHEN** a test validates an `issues` payload that holds no comment
- **THEN** the payload holds no comment and the fields of the issue event validate as before

### Requirement: The consumer refuses a comment it does not trust
The roadmap consumer SHALL refuse an `issue_comment` delivery before any GitHub request when its action is not `created`, when its sender login is the Service bot or ends with `[bot]`, when the issue carries a pull request marker, or when `comment.author_association` is outside `CONST_ROADMAP_TRUSTED_AUTHORS`. It SHALL answer the first three with `CONST_SERVICE_STATUS_COMMENT_REFUSED` and the untrusted author with `CONST_SERVICE_STATUS_UNTRUSTED_COMMENT`, which counts as `ignored`.

#### Scenario: A non-created comment
- **WHEN** a test delivers a signed `issue_comment` payload whose action is `edited` or `deleted`
- **THEN** the route answers `CONST_SERVICE_STATUS_COMMENT_REFUSED` and the fake GitHub client records no request

#### Scenario: A bot comment
- **WHEN** a test delivers a signed `issue_comment` payload whose sender login is the Service bot or ends with `[bot]`
- **THEN** the route answers `CONST_SERVICE_STATUS_COMMENT_REFUSED` and the fake GitHub client records no request

#### Scenario: An untrusted author comment
- **WHEN** a test delivers a signed `issue_comment` payload whose `author_association` is outside `CONST_ROADMAP_TRUSTED_AUTHORS`
- **THEN** the route answers `CONST_SERVICE_STATUS_UNTRUSTED_COMMENT`, counts the delivery as `ignored`, and the fake GitHub client records no request

#### Scenario: A pull request comment
- **WHEN** a test delivers a signed `issue_comment` payload whose issue carries a `pull_request` marker
- **THEN** the route answers `CONST_SERVICE_STATUS_COMMENT_REFUSED` and the fake GitHub client records no request

## MODIFIED Requirements

### Requirement: The consumer takes the pull request, review and check events
The event set of the roadmap consumer, `CONST_ROADMAP_WEBHOOK_EVENTS`, SHALL hold `issues`, `pull_request`, `pull_request_review`, `check_suite` and `issue_comment`, and step 8 of the roadmap-service runbook, `docs/CLUSTER.md`, SHALL name the same events. `CONST_ROADMAP_INTAKE_BATCH_KEYS` SHALL hold no comment key, so a comment runs no intake batch.

#### Scenario: The event set holds the pull, review and check events
- **WHEN** a test reads `CONST_ROADMAP_WEBHOOK_EVENTS`
- **THEN** the set holds `issues`, `pull_request`, `pull_request_review`, `check_suite` and `issue_comment`

#### Scenario: The runbook step and the event set name the same events
- **WHEN** a test reads `CONST_ROADMAP_WEBHOOK_EVENTS` and step 8 of `docs/CLUSTER.md`
- **THEN** each event of the set is named in that step
