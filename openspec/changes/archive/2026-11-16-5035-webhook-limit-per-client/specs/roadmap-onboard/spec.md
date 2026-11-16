## MODIFIED Requirements

### Requirement: A matching hook is present
The row SHALL report `present` when one active hook has `service.webhook_url`, the content type `json`, and events that hold each event of `CONST_ROADMAP_WEBHOOK_EVENTS`. The hook MAY send other events too.

#### Scenario: One active hook matches
- **WHEN** one active hook has the configured URL, `config.content_type` `json`, and the roadmap events
- **THEN** the row is `present` and names no field

#### Scenario: The hook sends more events than the Service takes
- **WHEN** one active hook has the configured URL, `config.content_type` `json`, and the events `issues`, `milestone`, `pull_request` and `release`
- **THEN** the row is `present`

#### Scenario: The hook does not send an event that the Service takes
- **WHEN** the only hook with the configured URL is active, has `json`, and sends `pull_request` and `release` only
- **THEN** the row is `wrong` and names `events`
