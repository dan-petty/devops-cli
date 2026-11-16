## MODIFIED Requirements

### Requirement: Watch maintains a ledger with failed head backoff
The watch row SHALL keep a ledger recording the pull request number, head SHA, verdict, the wait in minutes and the next read time. After the first failed read of a head it SHALL wait 15 minutes, SHALL double the wait after each later failed read of the same head, and SHALL hold the wait at 60 minutes. It SHALL clear the wait at once when the head commit or the base branch moves.

#### Scenario: Failed head is not re-read within 30 minutes
- **WHEN** a pull request head has failed checks and 10 minutes have elapsed
- **THEN** the row skips re-reading the checks and keeps the existing verdict

#### Scenario: Head change clears the backoff
- **WHEN** a new commit is pushed to a previously failed pull request
- **THEN** the row reads the new head immediately

#### Scenario: The first failed read of a head waits 15 minutes
- **WHEN** the row reads a head whose checks failed and the ledger holds no wait for that head
- **THEN** the ledger holds a wait of 15 minutes and a next read time 15 minutes after the read

#### Scenario: Each later failed read doubles the wait to 60 minutes
- **WHEN** the row reads the same failed head at the end of each recorded wait
- **THEN** the ledger holds waits of 30, 60 and 60 minutes after the three later reads

#### Scenario: A head with a running check keeps the normal cadence
- **WHEN** the row reads a pull request whose checks are still running
- **THEN** the ledger holds no wait and the next round reads the checks of that pull request
