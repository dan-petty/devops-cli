## ADDED Requirements

### Requirement: A stop with a pull request writes the status comment there
When a run stops and `self.pull` is set after the push, the run SHALL write the stop text to the pull request. The stop text SHALL name the stopped step and the failure class, and the pull request SHALL hold one comment for the run.

#### Scenario: A stop at a task group
- **WHEN** a run of a Staged item stops at `group 2` after it pushed the commits of group 1
- **THEN** the pull request holds one comment whose body holds `Stopped at group 2.` and `Failure class:`

#### Scenario: A stop with an amendment
- **WHEN** a run that applied an amendment stops
- **THEN** the pull request holds one comment, and it holds the bullet of the amendment

#### Scenario: A stop with no pull request
- **WHEN** the run has no pull request after the push
- **THEN** it writes the issue comment and no pull request comment

#### Scenario: A repeated stop of the run
- **WHEN** the same run stops a second time and the pull request holds its status comment
- **THEN** the run updates that comment and posts no second one
