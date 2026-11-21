## MODIFIED Requirements

### Requirement: A Planned item gets a new branch
For a Planned item the job SHALL make the branch `<type>/<issue>-<slug>` at `origin/<default branch>`. The type is the Conventional Commit type of the title of the item, and the slug is the one of the change folder. The job SHALL run the groups that have an unticked task, regenerate the documentation and archive the change, as it does for a Staged item.

#### Scenario: Two groups
- **WHEN** a Planned item has a change with two unticked groups on `origin/main`, both steps pass, and the checks pass
- **THEN** `origin` holds the new branch with one commit of the bot with the work of the run and one with the archive, GitHub received one draft pull request and one body that starts with `Closes #<issue>`, `gh pr ready` ran never, `implement.result` is `drafted`, the record holds `implement.branch` and `implement.pr`, and the Status is In Review

#### Scenario: A group that is done
- **WHEN** every task of group 1 is ticked on `origin/main`
- **THEN** the job runs a step for group 2 only

### Requirement: A publish that runs again keeps the draft of the run
`publish` SHALL record the draft of a new branch in `implement.pr` at once. A `publish` of the same run that runs again SHALL take the draft from the record, or update the open draft of the branch that the App opened, and open no second draft. An open pull request of the branch that another account opened SHALL stop the item, with no write to it and no delete of the branch. When GitHub refuses the draft, `publish` SHALL delete the branch only when the run made it: `prepare` found no branch.

#### Scenario: A publish that ended after the draft
- **WHEN** `publish` pushed the new branch and opened the draft, and its Job ended before the end of the run, and `publish` runs again
- **THEN** it takes the draft from `implement.pr`, opens no second draft and deletes no branch

#### Scenario: A publish that died before it recorded the draft
- **WHEN** the first `publish` opened the draft, and its Job ended before the mark `implement.pr`
- **THEN** the next `publish` finds the open draft of the branch, opens no second draft and keeps the branch

#### Scenario: A pull request of a person on the branch
- **WHEN** the first `publish` pushed the new branch and its Job ended before the draft, and a person then opened a pull request on the branch
- **THEN** the next `publish` stops the item, writes nothing to that pull request, opens no draft and keeps the branch

### Requirement: The job records the summary of the plan once
`prepare` SHALL record the summary of the plan in `implement.plan_summary` once, and a later Job SHALL take it from the record, because a push of `publish` puts the plan inside a commit of the bot. A title with the summary of the plan that holds a closing keyword SHALL give way to the summary of the title of the issue, because a squash merge puts the title in the subject. A title of the issue with a closing keyword SHALL stop the item before the push.

#### Scenario: A later Job of a Staged item
- **WHEN** the first Job of a Staged item stopped and pushed its work, and the next Job finishes the change
- **THEN** the title of the pull request is still the title with the summary of the plan

#### Scenario: A plan summary with a closing keyword
- **WHEN** the summary of the plan is `Fixes #4 in the job`
- **THEN** the title of the pull request is the title of the issue

#### Scenario: A title of the issue with a closing keyword
- **WHEN** the summary of the plan holds a closing keyword, and the title of the issue holds `closes #2336`
- **THEN** the item stops before the push, and `origin` keeps the branch as it was
