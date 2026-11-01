## ADDED Requirements

### Requirement: startup-import-probe-mechanism
The startup-import probe SHALL collect the set of loaded module names via sys.modules in the normal path, and SHALL use -X importtime only in the failure diagnostic path to report the ten slowest imports by cumulative seconds.

#### Scenario: normal probe uses sys.modules
- **WHEN** a startup-import probe runs and the budget passes
- **THEN** the probe collects module names from sys.modules without the -X importtime flag

#### Scenario: failure diagnostic uses importtime
- **WHEN** a startup-import probe runs and the budget fails
- **THEN** the probe re-runs with -X importtime and the assertion message includes the ten slowest imports by cumulative seconds
