## ADDED Requirements

### Requirement: Report does not crash on unparseable served_by
The report command SHALL NOT raise an unhandled ValueError when a ledger row holds a served_by value that urlsplit cannot parse.

#### Scenario: Ledger row with unparseable served_by
- **WHEN** A spend ledger row has served_by set to http://[::1 and the user runs devops ai cost report --by backend
- **THEN** The command exits 0 and prints the report table without a traceback

### Requirement: Unparseable backend shows as unknown
The report SHALL display the serving backend as unknown for a row whose served_by value urlsplit cannot parse.

#### Scenario: Backend column for unparseable value
- **WHEN** The report renders a row whose served_by is http://[::1
- **THEN** The backend column for that row shows unknown

### Requirement: Valid served_by values still resolve
The report SHALL resolve a valid served_by value to its local or hosted classification as before.

#### Scenario: Valid local backend still detected
- **WHEN** A ledger row has served_by set to http://localhost:11434 and the user runs devops ai cost report --by backend
- **THEN** The row is classified as local and the backend column shows the resolved value
