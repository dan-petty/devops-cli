## ADDED Requirements

### Requirement: The watch reads check runs and no commit status
The implement job watch SHALL judge the checks of its pull request head from the check runs and SHALL NOT send a request to the commit status endpoint, so a token without the `statuses` permission reads the checks. `devops pr monitor`, `devops pr ready` and `devops pr check-readiness` SHALL keep reading the commit statuses.

#### Scenario: The watch reads check runs
- **WHEN** the watch reads a pull request head whose one check run passed
- **THEN** the watch finds every check passed, and no request goes to the commit status endpoint

#### Scenario: The commit status endpoint refuses
- **WHEN** the commit status endpoint answers HTTP 403 and the check runs of the head passed
- **THEN** the watch finds every check passed, and the item does not stop for unread checks

#### Scenario: A check run fails
- **WHEN** a check run of the head failed
- **THEN** the watch reports that check as failed, and no request goes to the commit status endpoint

#### Scenario: A person's monitor reads the statuses
- **WHEN** `devops pr monitor` reads a head whose commit status endpoint answers HTTP 500
- **THEN** it exits 1
