## ADDED Requirements

### Requirement: The constructs row scans the docs theme tree
The constructs row SHALL scan the docs theme tree with the color literal rule, and that rule SHALL hold no ignores entry.

#### Scenario: The scan roots, the rule files and the rule
- **WHEN** A test reads the gate constants and the color literal rule
- **THEN** The scan roots hold the docs theme folder, the rule files of the rule hold the same glob, and the rule holds no ignores key
