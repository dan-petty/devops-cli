# roadmap-refine/context Specification

## ADDED Requirements

### Requirement: A slow identifier grep does not halt context collection
The context collection for cited identifiers in refine SHALL exclude archive and test fixture paths (`openspec/changes/archive`, `tests/fixtures`) and bound matches per file with `--max-count=5`. A git grep command that times out SHALL yield no matches for that identifier and SHALL NOT halt context collection or raise an unhandled exception.

#### Scenario: Git grep times out for a cited identifier
- **WHEN** an item cites an identifier whose git grep times out after 15 seconds
- **THEN** refine logs a warning, excludes matches for that identifier, and continues context collection with other cited context
