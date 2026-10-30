## ADDED Requirements

### Requirement: The Status follows the pull request that delivers the item
`devops pr create` SHALL set the Status of the open item that the new pull request closes to In Progress, and `devops pr ready` SHALL set it to In Review. A pull request that closes no open item of its repository SHALL change nothing.

#### Scenario: A draft that closes a Ready item
- **WHEN** a person runs `devops pr create` for a pull request that closes the Ready item 7
- **THEN** item 7 has the Status In Progress

#### Scenario: A ready pull request of an In Progress item
- **WHEN** a person runs `devops pr ready` for a pull request that closes the In Progress item 7
- **THEN** item 7 has the Status In Review

#### Scenario: A pull request that closes no item
- **WHEN** `devops pr create` runs for a pull request that closes no issue
- **THEN** no label changes

### Requirement: A Status moves forward only
In Progress SHALL replace no Status but New, Ready or none. In Review SHALL replace those and In Progress. A Blocked item SHALL stay Blocked.

#### Scenario: An item that is Blocked or already In Review
- **WHEN** `devops pr create` runs for a pull request that closes a Blocked item, or an item that is In Review
- **THEN** the Status of the item does not change

### Requirement: A failed Status write is reported
When the closing issues cannot be read or the Status cannot be written, the command SHALL exit 1 and name the pull request and the reason.

#### Scenario: The closing issues cannot be read
- **WHEN** the read of the closing issues fails with "HTTP 502"
- **THEN** the command exits 1 and its message names the reason

### Requirement: A closed issue holds no Status label
The workflow `.github/workflows/clear-status.yml` SHALL remove every `status/*` label of an issue when the issue closes, and SHALL remove no other label.

#### Scenario: A merge closes an issue
- **WHEN** an issue that holds `status/in-review` and `type/bug` closes
- **THEN** the workflow removes `status/in-review` and keeps `type/bug`
