# Spec Delta

## ADDED Requirements

### Requirement: gh-issues-milestones-labels-runs-request-plans
The 16 external-request commands in `gh issues`, `gh labels`, `gh milestones`, `gh runs`, `roadmap run`, and `survey` SHALL carry the `request-plan` dry-run class. Each command SHALL expose `--dry-run`, make zero external requests during a dry run, and output its planned requests.

#### Scenario: Dry run on gh issues create
- **WHEN** user executes `devops gh issues create --title "test" --dry-run`
- **THEN** no external request is made and the planned issue create request is printed

#### Scenario: Dry run on gh milestones list
- **WHEN** user executes `devops gh milestones list --dry-run`
- **THEN** no external request is made and the planned milestones listing request is printed

#### Scenario: Dry run on roadmap run
- **WHEN** user executes `devops roadmap run --dry-run`
- **THEN** no external request is made and the planned evaluation requests are printed

#### Scenario: Dry run on survey
- **WHEN** user executes `devops survey --dry-run`
- **THEN** no external request is made and the planned survey requests are printed
