## ADDED Requirements

### Requirement: One alert fires for a stuck item
The alert rules SHALL hold one alert that fires when an item has been in ready with a plan, or in blocked, longer than the configured time, and its message SHALL name the number of the item.

#### Scenario: The rule fires on a stuck item
- **WHEN** promtool test rules runs the group with a sample series over the threshold
- **THEN** The alert fires with the item number in its annotations

#### Scenario: The rule stays quiet on a fresh item
- **WHEN** promtool test rules runs the group with a sample series under the threshold
- **THEN** The alert does not fire
