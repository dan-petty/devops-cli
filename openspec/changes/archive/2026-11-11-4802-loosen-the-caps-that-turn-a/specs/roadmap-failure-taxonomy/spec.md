## MODIFIED Requirements

### Requirement: A failure class has a wait
The module `failure.py` SHALL hold the read-only mapping `RETRY_AFTER` from each class that `CLASS_BY_EXCEPTION` gives to a `timedelta`: `provider` 1 hour, `parser` 6 hours, `plan_defect` 1 hour, `ci_infra` 1 hour and `head_moved` 0. The keys of `RETRY_AFTER` SHALL be exactly the classes of `CLASS_BY_EXCEPTION`, and no value SHALL be `None`.

#### Scenario: The keys
- **WHEN** a test reads the keys of `RETRY_AFTER` and the classes of `CLASS_BY_EXCEPTION`
- **THEN** the two sets are equal

#### Scenario: The waits
- **WHEN** a test reads the value of each key
- **THEN** it finds 1 hour for `provider`, `plan_defect` and `ci_infra`, 6 hours for `parser`, and 0 for `head_moved`
