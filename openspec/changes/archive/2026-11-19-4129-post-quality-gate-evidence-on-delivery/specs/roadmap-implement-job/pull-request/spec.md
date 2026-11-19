## MODIFIED Requirements

### Requirement: A pull request that passes its checks is marked ready
When `draft_readiness` answers ready for the implement pull request and no review thread is open, the job SHALL publish the evidence comment of the head commit through `publish_pr_evidence`, and then run `gh pr ready` and set Status to In Review. When the answer is wait or refuse, or the publisher raises a `GitHubOperationError`, the job SHALL stop the item and SHALL NOT run `gh pr ready`. The job SHALL NOT merge.

#### Scenario: The finish
- **WHEN** the checks pass
- **THEN** the job writes one evidence comment that names the head commit before it runs `gh pr ready <pr>` once, Status is In Review, the record holds the number of the pull request, the last commit and the spend, and the issue holds one comment that starts with the marker and names the pull request

#### Scenario: A task group stays unticked
- **WHEN** the archived tasks file of the job holds an unticked task in group 2 after the archive step
- **THEN** the item is Blocked with a reason that names group 2, `gh pr ready` ran never, and the class of the failure is `plan_defect`

#### Scenario: A check starts after the watch
- **WHEN** a check run of the head is running when the job reads the check runs before it marks the pull request ready
- **THEN** the item is Blocked with the reason that a check runs, and `gh pr ready` ran never

#### Scenario: The evidence publisher fails
- **WHEN** `publish_pr_evidence` raises a `GitHubOperationError` for the head commit
- **THEN** the item is Blocked with the stop of the ready step, the record holds the stopped step, and `gh pr ready` ran never
