## MODIFIED Requirements

### Requirement: The comment and the record of a staged item
The job SHALL write one plan-state comment on the issue for each plan pull request, with the marker `<!-- devops roadmap stage -->` and a hidden key line that names the pull request. The state comment SHALL name the branch, the pull request, the groups with their tokens and the budget, and SHALL list the open findings and the advisory findings. A stage or a restage of a draft that has a state comment SHALL edit that comment in place and SHALL write no second state comment for it. Then the job SHALL post one comment of the run with a hidden event line that names the pull request: the facts of that run only, and no group and no finding. When the job replaced a draft pull request, the comment of the run SHALL name the number of that draft, and the record SHALL hold the re-stage in `stage.restage`. The job SHALL record `stage.branch`, `stage.pr`, `stage.sha` and `stage.text_hash` in the job record, and no copy of the groups. The job SHALL NOT change the Status of the item.

#### Scenario: The comment and the record
- **WHEN** The job stages a Ready bug
- **THEN** The issue gets a state comment with the branch, the pull request and the groups, and a comment of the run with no group, the record holds the four keys and no `stage.groups`, and the Status is still Ready

#### Scenario: The comment names the replaced draft
- **WHEN** The job replaces draft pull request 7 of item 7
- **THEN** The comment of the run of item 7 holds the number 7 and says that the job replaced that draft, and the record holds the re-stage of pull request 7

#### Scenario: A restage edits the state comment
- **WHEN** The item has a state comment for draft pull request 5, and the job replaces the plan of that draft
- **THEN** The issue holds one state comment for pull request 5 with the new groups, and one new comment of the run

#### Scenario: A title with no type
- **WHEN** The title of the item has no Conventional Commit type
- **THEN** The plan leaves the item out and says that its title has no type

### Requirement: The draft pull request gets the labels of its title
After the job records an item, it SHALL add to its draft pull request the `type/*` label and the `scope/*` label that the title gives, each only when `.github/labels.yml` on the default branch declares it. A label that GitHub refuses SHALL NOT delete the branch, close the draft or unset the record. The comment of the run SHALL name each label not added and the reason. Rejected credentials SHALL stop the run.

#### Scenario: The title gives a type and a scope
- **WHEN** the job stages item 1 and the labels file declares `type/docs` and `scope/openspec`
- **THEN** the draft holds `type/docs` and `scope/openspec` and no other label

#### Scenario: A label is refused and the branch stays
- **WHEN** GitHub refuses `type/docs` for the draft
- **THEN** the remote branch exists, the draft is open, and the record holds `stage.branch`, `stage.pr`, `stage.sha` and `stage.text_hash`

#### Scenario: A label is refused and the comment says so
- **WHEN** GitHub refuses `type/docs` for the draft and accepts `scope/openspec`
- **THEN** the comment of the run names the pull request, `type/docs` and the reason, and the draft holds `scope/openspec`

#### Scenario: Rejected credentials
- **WHEN** GitHub answers the label call with HTTP 401
- **THEN** the run stops with the unauthenticated error and the comment has no label note

#### Scenario: A dry run
- **WHEN** `devops roadmap stage --dry-run` runs
- **THEN** the plan lists the read of `.github/labels.yml` and the request that adds a label to the draft, and the run makes no request
