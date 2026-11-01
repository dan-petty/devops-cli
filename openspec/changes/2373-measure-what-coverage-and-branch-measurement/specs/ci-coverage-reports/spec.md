## ADDED Requirements

### Requirement: coverage-cost-benchmark-record
The change SHALL record the median CPU time and wall time of four coverage configurations (no coverage, lines, lines and branches, lines with ctrace core), each from three runs on a host with uptime under 2, and SHALL state the cost of branch measurement in seconds of CPU time and job time.

#### Scenario: benchmark table complete
- **WHEN** the three runs of each configuration complete on a host with uptime under 2
- **THEN** the results document contains a table with four rows, each showing the median user-plus-system CPU time and wall time

#### Scenario: branch cost stated in seconds
- **WHEN** the medians of the lines and lines-and-branches configurations are computed
- **THEN** the results document states the difference in seconds of CPU time and job time

### Requirement: coverage-report-options-cost
When the report or combine step is a large share of the lines configuration CPU time, the test job SHALL use coverage report options that reduce CPU time without lowering any coverage threshold.

#### Scenario: report option reduced without threshold change
- **WHEN** the report step is a large share of the lines configuration CPU time
- **THEN** the test job drops the term-missing report from the runner and the coverage floor value in pyproject.toml is unchanged
