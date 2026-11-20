## ADDED Requirements

### Requirement: A rejected plan's hold keeps only the paths that the tree holds
The record of a rejected plan MUST hold only the paths that the default branch holds, so a decimal, a version, a dotted setting or a domain ends no hold.

#### Scenario: A decimal and a version in the reason of a rejected plan
- **WHEN** the reason of a rejected plan names a decimal and a version before a file that the default branch holds, and `text_paths` reads the reason with the tree of the default branch
- **THEN** the record of `stage.rejected` holds that file and neither value
