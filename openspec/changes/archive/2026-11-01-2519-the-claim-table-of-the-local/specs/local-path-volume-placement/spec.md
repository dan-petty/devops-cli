## ADDED Requirements

### Requirement: version-keyed claim table
CHART_CLAIMS SHALL use a tuple of chart name and pinned version as its key type, and the set of keys SHALL equal the set returned by pinned_charts().

#### Scenario: key type and coverage check
- **WHEN** the test module is imported and CHART_CLAIMS is inspected
- **THEN** every key is a tuple of two strings, and the set of keys equals the set returned by pinned_charts()

### Requirement: version mismatch fails
A test SHALL fail when an Application pins a chart version that CHART_CLAIMS does not name.

#### Scenario: pinned version not in table
- **WHEN** pinned_charts() returns a (chart, version) pair that is not a key of CHART_CLAIMS
- **THEN** the test asserts a non-empty symmetric difference and fails
