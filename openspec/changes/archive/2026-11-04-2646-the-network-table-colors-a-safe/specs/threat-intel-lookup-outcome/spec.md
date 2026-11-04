## ADDED Requirements

### Requirement: The table colors a low-risk status green and a flagged status red
The table of network references SHALL color a status red when it holds the warning sign, holds "MALICIOUS", or holds "RISK" without "LOW". A status that holds "Low Risk" and neither the warning sign nor "MALICIOUS" SHALL be green, as any other safe status.

#### Scenario: A low-risk reference
- **WHEN** the table is built for a reference with the status "✓ Safe / Low Risk"
- **THEN** the status cell is "[green]✓ Safe / Low Risk[/green]"

#### Scenario: A flagged reference
- **WHEN** the table is built for a reference with the status "⚠️ Flagged (known botnet)" and for one with the status "High Risk"
- **THEN** both status cells are wrapped in "[red]" and "[/red]"
