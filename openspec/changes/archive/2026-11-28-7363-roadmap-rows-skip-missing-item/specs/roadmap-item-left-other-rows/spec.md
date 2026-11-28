## Purpose
Extend missing-issue (`GitHubNotAnIssueError`) handling to all remaining roadmap rows, submit and return helpers, GraphQL timeline reads, orphan plan pull requests, and 301 repository name redirects.

## ADDED Requirements

### Requirement: Implement row skips an item that left
The implement row SHALL leave out an item that left the repository with one log line, no failure class and no failure mark, and SHALL continue with its other items.

#### Scenario: Implement round with one item that left
- **WHEN** the implement row runs with `tests/support/fakes/roadmap_store.py` where one item left the repository and one other item remains
- **THEN** the round succeeds, writes one log line for the item that left, writes no failure class and no failure mark, and completes the other item

### Requirement: Stage row skips an item that left
The stage row SHALL leave out an item that left the repository with one log line, no failure class and no failure mark, and SHALL continue with its other items.

#### Scenario: Stage round with one item that left
- **WHEN** the stage row runs with `tests/support/fakes/roadmap_store.py` where one item left the repository and one other item remains
- **THEN** the round succeeds, writes one log line for the item that left, writes no failure class and no failure mark, and completes the other item

### Requirement: Watch row skips an item that left
The watch row SHALL leave out an item that left the repository with one log line, no failure class and no failure mark, and SHALL continue with its other items.

#### Scenario: Watch round with one item that left
- **WHEN** the watch row runs with `tests/support/fakes/roadmap_store.py` where one item left the repository and one other item remains
- **THEN** the round succeeds, writes one log line for the item that left, writes no failure class and no failure mark, and completes the other item

### Requirement: Open row skips an item that left
The open row SHALL leave out an item that left the repository with one log line, no failure class and no failure mark, and SHALL continue with its other items.

#### Scenario: Open round with one item that left
- **WHEN** the open row runs with `tests/support/fakes/roadmap_store.py` where one item left the repository and one other item remains
- **THEN** the round succeeds, writes one log line for the item that left, writes no failure class and no failure mark, and completes the other item

### Requirement: Refine row skips an item that left
The refine row SHALL leave out an item that left the repository with one log line, no failure class and no failure mark, and SHALL continue with its other items.

#### Scenario: Refine round with one item that left
- **WHEN** the refine row runs with `tests/support/fakes/roadmap_store.py` where one item left the repository and one other item remains
- **THEN** the round succeeds, writes one log line for the item that left, writes no failure class and no failure mark, and completes the other item

### Requirement: Retitle row skips an item that left
The retitle row SHALL leave out an item that left the repository with one log line, no failure class and no failure mark, and SHALL continue with its other items.

#### Scenario: Retitle round with one item that left
- **WHEN** the retitle row runs with `tests/support/fakes/roadmap_store.py` where one item left the repository and one other item remains
- **THEN** the round succeeds, writes one log line for the item that left, writes no failure class and no failure mark, and completes the other item

### Requirement: Fix-plan row skips an item that left
The fix-plan row SHALL leave out an item that left the repository with one log line, no failure class and no failure mark, and SHALL continue with its other items.

#### Scenario: Fix-plan round with one item that left
- **WHEN** the fix-plan row runs with `tests/support/fakes/roadmap_store.py` where one item left the repository and one other item remains
- **THEN** the round succeeds, writes one log line for the item that left, writes no failure class and no failure mark, and completes the other item

### Requirement: Intake read drops a record that is no issue
The intake read SHALL drop the record of a number that is no issue, SHALL write one log line, and SHALL continue with its other records.

#### Scenario: Intake read with one number that is no issue
- **WHEN** the intake read in `src/devops_cli/roadmap/intake/intake.py` gets `GitHubNotAnIssueError` for one number and another candidate remains
- **THEN** the read drops the record of that number, writes one log line, and returns the decision for the other candidate

### Requirement: Metrics omits the age of an item that left
The metrics row SHALL omit the age of an item that left the repository without a failure and SHALL continue with its other items.

#### Scenario: Metrics round with one item that left
- **WHEN** the metrics row reads item ages and the store raises `GitHubNotAnIssueError` for one item
- **THEN** the row succeeds, writes one log line, omits the age for that item, and reports the ages of the other items

### Requirement: Error class for an item that left
`implement_submit._fresh` and `return_item.plan_return` MUST raise `GitHubNotAnIssueError` when an item left the repository, not `LookupError` and not a bare `DevOpsCLIError`.

#### Scenario: An item that left reaches the submit and return calls
- **WHEN** the store reports that an item left the repository to `implement_submit._fresh` and `return_item.plan_return`
- **THEN** each call raises `GitHubNotAnIssueError`

### Requirement: Plan drift catches only an item that left
The plan drift handler SHALL catch `GitHubNotAnIssueError` and SHALL NOT treat another `GitHubNotFoundError` as an item that left.

#### Scenario: Plan drift sees a missing object that is not an issue
- **WHEN** plan drift receives `GitHubNotFoundError` for a missing object that is not an issue
- **THEN** the handler closes no pull request, logs no left-issue warning, and the `GitHubNotFoundError` propagates

### Requirement: Stage row closes an orphan plan pull request
The plan drift handler SHALL close a plan pull request whose issue left the repository and SHALL write one log line.

#### Scenario: Plan drift finds a plan pull request whose issue left
- **WHEN** plan drift receives `GitHubNotAnIssueError` for a plan pull request whose issue left
- **THEN** the handler closes that pull request and writes one log line

### Requirement: Repository name read follows a 301
A test MUST cover a 301 answer of the read of the repository name, and `GitHubClient` MUST return the name at the redirect target.

#### Scenario: Repository name read gets a 301
- **WHEN** `GitHubClient` reads the repository name and the session answers 301 to a new location
- **THEN** the client follows the redirect and accepts the renamed repository
