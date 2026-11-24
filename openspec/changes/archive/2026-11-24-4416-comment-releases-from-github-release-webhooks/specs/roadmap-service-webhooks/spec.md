## ADDED Requirements

### Requirement: The payload holds the release fields
The model `GitHubWebhookPayload` SHALL parse the optional `release` object of a `release` delivery into `WebhookRelease`, with the fields `tag_name`, `html_url`, `body`, `draft`, `prerelease` and `published_at`. `published_at` SHALL be optional, so a delivery of a draft still validates and reaches the refusal instead of answering 400. The model SHALL ignore every other field of the release object.

#### Scenario: A published release payload parses
- **WHEN** a test validates a `release` payload with the action `published` and the six release fields
- **THEN** the payload release holds the tag, the URL and the body, and `draft` and `prerelease` are false

### Requirement: The consumer refuses an unwanted release delivery
The roadmap consumer SHALL refuse a `release` delivery before any GitHub request when its action is not `published`, when the release is a draft, when it is a prerelease, or when it carries no publication time. It SHALL answer each with `CONST_SERVICE_STATUS_RELEASE_REFUSED`, which counts as `ignored`, and SHALL queue no round and no scoped update.

#### Scenario: An unwanted release is refused
- **WHEN** a test sends a signed `release` delivery with the action `created`, one of a draft, one of a prerelease and one whose release holds no publication time
- **THEN** each delivery is answered with `CONST_SERVICE_STATUS_RELEASE_REFUSED`, the lanes queue no round, and the fake GitHub client records no request

## MODIFIED Requirements

### Requirement: The consumer takes the pull request, review, check and release events
The event set of the roadmap consumer, `CONST_ROADMAP_WEBHOOK_EVENTS`, SHALL hold `issues`, `pull_request`, `pull_request_review`, `check_suite`, `issue_comment` and `release`, and step 8 of the roadmap-service runbook, `docs/CLUSTER.md`, SHALL name the same events. `CONST_ROADMAP_INTAKE_BATCH_KEYS` SHALL hold no comment key and no release key, so a comment and a release run no intake batch.

#### Scenario: The event set holds the pull, review and check events
- **WHEN** a test reads `CONST_ROADMAP_WEBHOOK_EVENTS`
- **THEN** the set holds `issues`, `pull_request`, `pull_request_review`, `check_suite` and `issue_comment`

#### Scenario: The runbook step and the event set name the same events
- **WHEN** a test reads `CONST_ROADMAP_WEBHOOK_EVENTS` and step 8 of `docs/CLUSTER.md`
- **THEN** each event of the set is named in that step

#### Scenario: The event set holds the pull, review, check and release events
- **WHEN** a test reads `CONST_ROADMAP_WEBHOOK_EVENTS`
- **THEN** the set holds `issues`, `pull_request`, `pull_request_review`, `check_suite`, `issue_comment` and `release`

## RENAMED Requirements

- FROM: `### Requirement: The consumer takes the pull request, review and check events`
- TO: `### Requirement: The consumer takes the pull request, review, check and release events`
