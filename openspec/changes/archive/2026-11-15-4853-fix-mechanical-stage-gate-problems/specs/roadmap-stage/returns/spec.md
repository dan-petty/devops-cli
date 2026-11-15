## ADDED Requirements

### Requirement: Mechanical edits before the model
The stage job SHALL apply every mechanical finding of a refused reply before it sends the remaining findings of that reply to the model.

#### Scenario: One mechanical and one model finding
- **WHEN** A refused reply holds a dependencies finding and a finding that needs the model
- **THEN** The dependencies edit is applied, the gate runs again, and the model receives only the findings that remain
