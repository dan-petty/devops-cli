## ADDED Requirements

### Requirement: The table builder parses only the modules that name the registry
The table builder SHALL read the text of each test module, and MUST NOT parse a module whose text does not hold `REGISTRY_COUNTS`. A module that holds the name only outside a module-level assignment, such as in a comment, SHALL give no entry.

#### Scenario: A module with no declaration is not parsed
- **WHEN** `counts_in` reads a test module whose text does not hold `REGISTRY_COUNTS`.
- **THEN** It returns no entry, and `ast.parse` gets no call for the text of that module.

#### Scenario: The name in a comment gives no entry
- **WHEN** `counts_in` reads a test module that holds `REGISTRY_COUNTS` only in a comment.
- **THEN** It returns no entry.
