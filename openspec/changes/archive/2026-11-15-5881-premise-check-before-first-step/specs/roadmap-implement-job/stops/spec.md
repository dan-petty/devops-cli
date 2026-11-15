## ADDED Requirements

### Requirement: The job checks the premise of every open behavior group before the first step
The job SHALL check the premise of each open behavior group once in a run, at the first group boundary, after the claim check and before the first step. An open group has a task that is not ticked. The check SHALL read the last commit of the checkout that is no `wip:` commit at that boundary. A later group boundary of the run SHALL make no premise check. The comment of the return SHALL say that the run made no model request and wrote no code.

#### Scenario: A false premise of a late group
- **WHEN** a plan has 3 groups, behavior group 3 adds a guard that the branch defines, and groups 1 and 2 are open
- **THEN** the job returns the item to New before the step of group 1: it makes no model request, pushes no checkpoint, closes no pull request, and the comment names the guard and says that the run made no model request

#### Scenario: A guard of a group that passed in an earlier Job
- **WHEN** an earlier Job passed behavior group 1, which added `_delivery_title`, and group 2 is open
- **THEN** the job checks no premise of group 1, runs group 2, and marks the pull request ready
