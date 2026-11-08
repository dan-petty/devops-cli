## ADDED Requirements

### Requirement: The Service shows each state record that it could not write
`devops_cli_service_state_unkept` SHALL be 1, with the label `record` set to `budget`, `halt` or `ledger`, after the last write of that record failed, and 0 after the next write of that record that works. A failed write SHALL stay one error log line, and the Service MUST NOT raise from the write. The first write of a record SHALL create the series of that record, and a record that was never written SHALL have no series.

#### Scenario: A budget write error
- **WHEN** the budget record cannot be written and a request is admitted, then the record can be written and the next request is admitted
- **THEN** `admit` raises nothing, one error log line names the record, the series `budget` reads 1, then 0, and the series of the other records do not exist

#### Scenario: A halt write error
- **WHEN** GitHub refuses the identity and the halt record cannot be written
- **THEN** the Service is halted in memory, and the series `halt` reads 1

#### Scenario: A ledger write error
- **WHEN** a job fails a round and the ledger record cannot be written, then the record can be written and the job succeeds
- **THEN** the round is counted in memory, the series `ledger` reads 1, then 0

#### Scenario: A record that cannot be read
- **WHEN** the ledger record holds text that is not a record at start
- **THEN** the start fails with an error that names the file, and the gauge has no series
