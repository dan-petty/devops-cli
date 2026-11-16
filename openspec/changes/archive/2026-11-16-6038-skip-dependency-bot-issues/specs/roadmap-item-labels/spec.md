## MODIFIED Requirements

### Requirement: An Item is an issue with a priority label
The roadmap store SHALL list as Items the issues of the repository, open and closed and never pull requests, that hold a `priority/*` label of the family. It SHALL list as Candidates the open issues that hold none. Neither list, nor the issues that intake reads, SHALL hold an issue whose author login is in `roadmap.skip_authors`, whose default is the bot of the Renovate App.

#### Scenario: Items and Candidates
- **WHEN** the repository holds an open issue with `priority/p2-medium`, a closed issue with `priority/p3-low`, an open issue with no `priority/*` label and a pull request with `priority/p1-high`
- **THEN** the Items are the two issues with a priority label, and the one Candidate is the open issue without one

#### Scenario: The Dependency Dashboard of Renovate
- **WHEN** `dan-petty-renovate[bot]` opened an open issue with `priority/p2-medium` and an open issue with no `priority/*` label, and a person opened the same two issues
- **THEN** the Items and the Candidates hold only the issues of the person, and the rows intake, retitle, refine, alternatives, stage, implement, open and metrics name no issue of the bot

#### Scenario: The setting names the bots
- **WHEN** `roadmap.skip_authors` holds only `another-tool[bot]`
- **THEN** an issue of `another-tool[bot]` is no Item, and an issue of `dan-petty-renovate[bot]` or of `another-tool[bot]x` is one; with an empty list, no issue is left out for its author
