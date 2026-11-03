## ADDED Requirements

### Requirement: The draft pull request gets the labels of its title
After the job records an item, it SHALL add to its draft pull request the `type/*` label and the `scope/*` label that the title gives, each only when `.github/labels.yml` on the default branch declares it. A label that GitHub refuses SHALL NOT delete the branch, close the draft or unset the record. The comment of the item SHALL name each label not added and the reason. Rejected credentials SHALL stop the run.

#### Scenario: The title gives a type and a scope
- **WHEN** the job stages item 1 and the labels file declares `type/docs` and `scope/openspec`
- **THEN** the draft holds `type/docs` and `scope/openspec` and no other label

#### Scenario: A label is refused and the branch stays
- **WHEN** GitHub refuses `type/docs` for the draft
- **THEN** the remote branch exists, the draft is open, and the record holds `stage.branch`, `stage.pr`, `stage.sha` and `stage.groups`

#### Scenario: A label is refused and the comment says so
- **WHEN** GitHub refuses `type/docs` for the draft and accepts `scope/openspec`
- **THEN** the one comment of the item names the pull request, `type/docs` and the reason, and the draft holds `scope/openspec`

#### Scenario: Rejected credentials
- **WHEN** GitHub answers the label call with HTTP 401
- **THEN** the run stops with the unauthenticated error and the comment has no label note

#### Scenario: A dry run
- **WHEN** `devops roadmap stage --dry-run` runs
- **THEN** the plan lists the read of `.github/labels.yml` and the request that adds a label to the draft, and the run makes no request

## MODIFIED Requirements

### Requirement: A failed write stops one item
A write that fails, also the comment on an item stopped on the budget, SHALL stop its item with the reason and SHALL NOT stop the other writes. The job SHALL fail after the other writes and name each item that failed. The labels of the draft pull request are the one exception: a label that GitHub refuses stops no item (requirement "The draft pull request gets the labels of its title").

#### Scenario: The comment of a stopped item fails
- **WHEN** two items stop on the budget and the comment on the first fails
- **THEN** the second item still gets its comment and its record, the first item gets no record, and the error names the first item
