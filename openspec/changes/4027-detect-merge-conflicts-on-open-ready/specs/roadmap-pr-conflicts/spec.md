## Purpose
The Service row `pr_conflicts` finds each ready delivery pull request that has merge conflicts with the default branch, comments once on it, and sends a gauge of those pull requests, because GitHub sends no event for a conflict that a merge into the default branch makes.

## ADDED Requirements

### Requirement: The status lane runs the conflict row last
The status lane SHALL hold a row named `pr_conflicts` after `cloudflare_status`. The row SHALL need no clone, SHALL call no model, and SHALL be due on a first run and every `DEFAULT_ROADMAP_PR_CONFLICTS_INTERVAL_MINUTES` minutes.

#### Scenario: The status lane table
- **WHEN** the status lane table is read
- **THEN** its last two rows are `cloudflare_status` and `pr_conflicts`, and `pr_conflicts` needs no clone and is due on a first run

### Requirement: The row judges only delivery pull requests
The row SHALL read no draft. It SHALL judge only an open pull request that is not a draft, merges into the default branch of its repository, and whose body closes exactly one issue that is an open Item.

#### Scenario: A plan pull request
- **WHEN** an open pull request into the default branch has merge conflicts and closes no issue
- **THEN** the row posts no comment

#### Scenario: A draft
- **WHEN** an open draft has merge conflicts and closes one open Item
- **THEN** the row sends no read of it and posts no comment

#### Scenario: Another base branch
- **WHEN** an open pull request into a branch that is not the default branch has merge conflicts
- **THEN** the row posts no comment

#### Scenario: Two closed issues
- **WHEN** an open pull request with merge conflicts closes two issues
- **THEN** the row posts no comment

#### Scenario: A closed Item
- **WHEN** an open pull request with merge conflicts closes an Item that is closed
- **THEN** the row posts no comment

### Requirement: A conflict gets one comment
When GitHub reports a merge conflict for a delivery pull request, the row SHALL post one comment on it that names the default branch and the head commit. It SHALL post no second comment while the ledger `pr_conflicts.json` records the same head commit.

#### Scenario: A dirty mergeable state
- **WHEN** the read returns `mergeable` false with `mergeable_state` `dirty`
- **THEN** the row posts the conflict comment on the pull request and none on the issue

#### Scenario: The conflict persists
- **WHEN** the row runs twice and both reads report the conflict at the same head commit
- **THEN** the pull request holds one conflict comment

#### Scenario: A new head commit
- **WHEN** the second read reports the conflict at a new head commit
- **THEN** the row posts a second comment that names the new head commit

### Requirement: A conflict that returns gets the comment again
The row SHALL drop the ledger entry of a delivery pull request that GitHub reports with no conflict, so a conflict that returns at the same head commit gets the comment once more.

#### Scenario: The conflict returns
- **WHEN** three rounds read a conflict, then a clean state, then the conflict again at the same head commit
- **THEN** the pull request holds two conflict comments

### Requirement: An unknown state changes nothing
When GitHub has not computed the mergeable state, the row SHALL post no comment and SHALL keep the ledger entry of the pull request, and the next round SHALL read the pull request again.

#### Scenario: An unknown mergeable state
- **WHEN** the reads return `unknown`, a conflict, `unknown` and the conflict again at the same head commit
- **THEN** the first round posts no comment and the four rounds post one conflict comment

### Requirement: A clean pull request that is behind gets no action
When a delivery pull request has no conflict and is behind the default branch, the row SHALL send no update-branch request and SHALL post no comment.

#### Scenario: A pull request behind the default branch
- **WHEN** the read returns `mergeable` true with `mergeable_state` `behind`
- **THEN** the only request of the round is the read of the pull request

### Requirement: The conflict gauge
At the end of each round the row SHALL send the gauge `devops_cli_roadmap_conflicted_pulls` with the number of delivery pull requests that have merge conflicts, labelled with the repository.

#### Scenario: Two conflicted pull requests
- **WHEN** a round reads two delivery pull requests with conflicts, one clean and one unknown
- **THEN** the gauge records 2 for the repository

### Requirement: A failed read fails the row
When a read of GitHub fails, the row SHALL raise. When the ledger exists and cannot be read, the row SHALL raise `RoadmapRunError` that names the file, and SHALL send no request.

#### Scenario: A failed read of a pull request
- **WHEN** GitHub answers 404 for the read of an open pull request
- **THEN** the row raises `GitHubNotFoundError`

#### Scenario: An unreadable ledger
- **WHEN** `pr_conflicts.json` holds text that is not JSON
- **THEN** the row raises `RoadmapRunError` with the path of the ledger, and sends no request
