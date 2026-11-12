## MODIFIED Requirements

### Requirement: gh-issues-milestones-labels-runs-request-plans
The 16 external-request commands in `gh issue`, `gh label`, `gh milestones`, `gh run`, `roadmap run`, and `survey` SHALL carry the `request-plan` dry-run class. Each command SHALL expose `--dry-run`, make zero external requests during a dry run, and output its planned requests.

#### Scenario: Dry run on gh issues create
- **WHEN** user executes `devops gh issue create --title "test" --dry-run`
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

### Requirement: gh-api-status-branch-protection-secrets-request-plans
The nine external-request commands in `gh api`, `gh branch-protection audit`, `gh branch-protection sync`, `gh metrics`, `gh rate-limit`, `gh secret list`, `gh secret sync`, `gh status`, and `status` SHALL carry the `request-plan` dry-run class. Each command SHALL expose `--dry-run`, make zero external requests during a dry run, and output its planned requests.

#### Scenario: Dry run on gh api
- **WHEN** user executes `devops gh api repos/:owner/:repo/issues --dry-run`
- **THEN** no external request is made and the planned api request is printed

#### Scenario: Dry run on gh rate-limit
- **WHEN** user executes `devops gh rate-limit --dry-run`
- **THEN** no external request is made and the planned rate_limit request is printed

#### Scenario: Dry run on gh branch-protection sync
- **WHEN** user executes `devops gh branch-protection sync --dry-run`
- **THEN** no external request is made, no remote branch protection is fetched, and planned protection requests are printed

#### Scenario: Dry run on gh secrets sync
- **WHEN** user executes `devops gh secret sync -n TOKEN --dry-run`
- **THEN** no external request is made, OS Keyring and Vault are not accessed, and planned secret upload requests are printed

#### Scenario: Dry run on status
- **WHEN** user executes `devops status --dry-run`
- **THEN** no external HTTP request is made and planned statuspage requests are printed
