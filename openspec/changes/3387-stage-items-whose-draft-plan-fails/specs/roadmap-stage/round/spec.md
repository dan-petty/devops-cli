## ADDED Requirements

### Requirement: The stage job replaces a draft pull request in place
The stage job SHALL push the new plan commit to the branch of the draft pull request that it replaces, with a lease on the commit it recorded, and SHALL set the title and body of that draft. It SHALL open no second pull request, and it SHALL name the replaced draft in the comment of the item.

#### Scenario: The draft of a replaced plan
- **WHEN** The job stages item 7 and its target carries draft pull request 7
- **THEN** The branch head is the new plan commit, the title and body of pull request 7 are the new ones, and item 7 has one open pull request

#### Scenario: A person moved the branch
- **WHEN** A person pushed a commit to the branch after the job recorded the staged commit
- **THEN** The push with the lease is refused, the job stops item 7 with the error of the push, and it opens no second pull request

## MODIFIED Requirements

### Requirement: The comment and the record of a staged item
The job SHALL post one comment on the issue with the marker `<!-- devops roadmap stage -->` that names the branch, the pull request, the groups and the budget. When the job replaced a draft pull request, the comment SHALL name the number of that draft, and the record SHALL hold the re-stage in `stage.restage`. The job SHALL record `stage.branch`, `stage.pr`, `stage.sha` and `stage.groups` in the job record. The job SHALL NOT change the Status of the item.

#### Scenario: The comment and the record
- **WHEN** The job stages a Ready bug
- **THEN** The issue gets one comment with the marker, the record holds the four keys, and the Status is still Ready

#### Scenario: The comment names the replaced draft
- **WHEN** The job replaces draft pull request 7 of item 7
- **THEN** The comment of item 7 holds the number 7 and says that the job replaced that draft, and the record holds the re-stage of pull request 7

#### Scenario: A title with no type
- **WHEN** The title of the item has no Conventional Commit type
- **THEN** The plan leaves the item out and says that its title has no type
