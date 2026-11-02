## ADDED Requirements

### Requirement: The implement job watch reads check runs only
The implement job watch SHALL read the check runs of its pull request head through `read_check_runs` and SHALL NOT call the commit status API endpoint.

#### Scenario: The watch reads check runs
- **WHEN** The implement job watch reads the checks of its pull request
- **THEN** It calls `read_check_runs` and sends no request to the commit status endpoint

#### Scenario: A token without the statuses permission
- **WHEN** The App token holds no `statuses` permission and the watch reads the checks
- **THEN** The read returns the check run items and no unread reason
