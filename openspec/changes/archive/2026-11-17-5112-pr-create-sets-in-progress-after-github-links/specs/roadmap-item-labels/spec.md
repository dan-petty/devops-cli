## MODIFIED Requirements

### Requirement: The Status follows the pull request that delivers the item

`devops pr create` SHALL set the Status of the open item that the new pull request closes to In
Progress, and `devops pr ready` SHALL set it to In Review. GitHub links the closing issue after
the pull request opens, so `devops pr create` SHALL read the closing issues again for a bounded
time until one is linked. When the bounded time ends with no linked issue, the command SHALL
warn that it found no closing issue and SHALL exit 0. A pull request that closes no open item of
its repository SHALL change nothing. The function that writes the Status SHALL return the number
of the issue whose Status it sets, and None when it sets none.

#### Scenario: A draft that closes a Ready item

- **WHEN** a person runs `devops pr create` for a pull request that closes the Ready item 7
- **THEN** item 7 has the Status In Progress

#### Scenario: The link appears after the first read

- **WHEN** the first read of the closing issues returns no issue and the second returns item 7
- **THEN** `devops pr create` sets item 7 to In Progress

#### Scenario: No closing issue appears

- **WHEN** every read of the closing issues returns no issue before the bounded time ends
- **THEN** the command warns that it found no closing issue and exits 0

#### Scenario: A ready pull request of an In Progress item

- **WHEN** a person runs `devops pr ready` for a pull request that closes the In Progress item 7
- **THEN** item 7 has the Status In Review

#### Scenario: A pull request that closes no item

- **WHEN** `devops pr create` runs for a pull request that closes no issue
- **THEN** no label changes
