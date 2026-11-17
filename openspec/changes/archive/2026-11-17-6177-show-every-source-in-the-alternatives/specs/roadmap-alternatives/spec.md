## REMOVED Requirements

### Requirement: The comment shows at most five sources
**Reason**: The bound left sources out of the context that refine, stage and implement read, and the owner forbids caps that lose context (2026-11-17, #6177).
**Migration**: The requirement "The comment shows every source" lists each source in the closed block.

## ADDED Requirements

### Requirement: The comment shows every source
The folded block of the comment SHALL show every source of the reply, and SHALL leave none out.

#### Scenario: More than five sources
- **WHEN** the reply cites eight sources that the tools returned
- **THEN** the folded block shows all eight, no source is outside the block, and the comment has no line that counts sources left out
