## ADDED Requirements

### Requirement: The probe names the test module of a cited function
The stage probe SHALL name, for each cited identifier that the staging commit defines, the test modules whose text holds the name as a word, and SHALL say that no test module names the identifier when none does. It SHALL read the test modules of all cited identifiers with one git command, and SHALL say so when its command bound leaves the listing out.

#### Scenario: A cited function has a test module
- **WHEN** the issue cites a function whose name a test module of the staging commit holds
- **THEN** the probes text holds a line that names that test module for the function

#### Scenario: A cited function has no test module
- **WHEN** no test module of the staging commit holds the name of a cited function
- **THEN** the probes text holds a line that says that no test module names the function

#### Scenario: The command bound leaves the listing out
- **WHEN** the probe has no git command left when it reads the test modules
- **THEN** the probes text holds a line that says that the bound left the test module listing out
