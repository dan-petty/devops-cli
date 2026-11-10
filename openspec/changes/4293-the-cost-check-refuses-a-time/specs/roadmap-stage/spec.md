## ADDED Requirements

### Requirement: A build cost states its time in minutes, hours, days or weeks
The stage job SHALL accept a time in `existing_tool` of a plan that sets `builds_own` to true when it is a number of minutes, hours, days or weeks, written with digits or with a number word from one to twelve, `a` or `an`. It SHALL still refuse a text that gives no count of tokens or no count of time.

#### Scenario: A time in days with a number word
- **WHEN** `builds_own` is true and `existing_tool` is `Cost: 80k tokens and about two days of elapsed time.`
- **THEN** `check_proposal` returns no cost problem.

#### Scenario: A time in weeks with digits
- **WHEN** `builds_own` is true and `existing_tool` is `Cost: 120k tokens, 1.5 weeks.`
- **THEN** `check_proposal` returns no cost problem.

#### Scenario: A time with no count
- **WHEN** `builds_own` is true and `existing_tool` is `Cost: 80k tokens and some days.`
- **THEN** `check_proposal` returns a problem that names the cost rule.
