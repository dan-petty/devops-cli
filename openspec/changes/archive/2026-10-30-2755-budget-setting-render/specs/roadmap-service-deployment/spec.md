## ADDED Requirements

### Requirement: A deploy keeps the hourly request budget
The ConfigMap that a deploy renders SHALL hold `service.github_requests_per_hour` when the active settings set it, and SHALL hold no such key when they do not.

#### Scenario: The active settings set the budget
- **WHEN** the active settings set `service.github_requests_per_hour` to 2000 and the ConfigMap is rendered
- **THEN** the `service` section of the rendered config holds `github_requests_per_hour: 2000`

#### Scenario: The active settings keep the default
- **WHEN** the active settings set no `service.github_requests_per_hour` and the ConfigMap is rendered
- **THEN** the `service` section of the rendered config holds no `github_requests_per_hour`
