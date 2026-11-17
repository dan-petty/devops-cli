## ADDED Requirements

### Requirement: Store-derived taxonomy
The metrics collector SHALL derive taxonomy counts from the open Items that the roadmap store holds.

#### Scenario: No second open issue listing
- **WHEN** One metrics round runs for a repository with a roadmap store.
- **THEN** The collector sends no request to `repos/<repo>/issues?state=open` and the taxonomy counts match the labels of the open Items in the store.

### Requirement: Session-based workflow run read
The metrics collector SHALL read workflow runs through the GitHub session that sends conditional requests.

#### Scenario: Workflow runs use the session
- **WHEN** The metrics collector reads workflow runs for a repository.
- **THEN** The read goes through the session and makes no uncached `gh api repos/<repo>/actions/runs` call.

### Requirement: Session-based milestone read
The metrics collector SHALL read milestones through the GitHub session that sends conditional requests.

#### Scenario: Milestones use the session
- **WHEN** The metrics collector reads milestones for a repository.
- **THEN** The read goes through the session and makes no uncached `gh api repos/<repo>/milestones` call.
