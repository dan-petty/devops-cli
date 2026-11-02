## ADDED Requirements

### Requirement: Safe low-risk status renders green
A network reference whose security_status holds the text 'Low Risk' SHALL be colored green.

#### Scenario: Safe low-risk reference renders green
- **WHEN** A NetworkReference has security_status of '✓ Safe / Low Risk'
- **THEN** The status cell in the table row is wrapped in [green]...[/green] markup

### Requirement: Flagged status renders red
A network reference whose security_status holds '⚠️' or 'MALICIOUS' or 'RISK' without 'LOW' SHALL be colored red.

#### Scenario: High-risk reference renders red
- **WHEN** A NetworkReference has security_status of '⚠️ High Risk Detected'
- **THEN** The status cell in the table row is wrapped in [red]...[/red] markup

### Requirement: Unchecked status renders yellow
A network reference whose security_status holds 'UNCHECKED' and does not hold a red trigger SHALL be colored yellow.

#### Scenario: Unchecked reference renders yellow
- **WHEN** A NetworkReference has security_status of 'Unchecked'
- **THEN** The status cell in the table row is wrapped in [yellow]...[/yellow] markup
