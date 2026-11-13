## REMOVED Requirements

### Requirement: gh-project-views-pages-request-plans
**Reason**: It counted ten commands, and its scenario ran `devops gh pages build`, which #5212 deletes with `devops gh pages builds`.
**Migration**: The requirement "gh-project-views-pages-dry-run-request-plans" holds the same rule for the eight commands that stay.

## ADDED Requirements

### Requirement: gh-project-views-pages-dry-run-request-plans
The eight external-request commands in `gh project`, `gh views`, and `gh pages` SHALL carry the `request-plan` dry-run class. Each command SHALL expose `--dry-run`, make zero external requests during a dry run, and output its planned requests.

#### Scenario: Dry run on gh pages status
- **WHEN** user executes `devops gh pages status --dry-run`
- **THEN** no external request is made and the planned status request is printed

#### Scenario: Dry run on gh project sync
- **WHEN** user executes `devops gh project sync --dry-run`
- **THEN** no external request is made and the planned board, field, and view requests are printed
