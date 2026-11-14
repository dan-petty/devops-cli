## ADDED Requirements

### Requirement: The verification prompt names the rejected alternatives
The stage verification prompt SHALL name the rejected alternatives of the plan and the false premise finding that a fact the repository contradicts requires.

#### Scenario: The verification prompt holds the rule
- **WHEN** A test reads the stage verification prompt
- **THEN** The text names the rejected alternatives and the false premise finding
