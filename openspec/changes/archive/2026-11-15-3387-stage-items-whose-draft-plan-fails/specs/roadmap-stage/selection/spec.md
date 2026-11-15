## ADDED Requirements

### Requirement: The stage job re-stages a failing draft plan once
The stage job SHALL re-stage a draft plan that fails the plan check once, and it SHALL hold the item after that while the text of the item is unchanged, with a reason that names the failed `check_proposal`.

#### Scenario: A second failing plan
- **WHEN** The job record of item 7 holds a re-stage of its draft pull request, the text of item 7 is unchanged, and its draft plan fails `check_proposal` again
- **THEN** The selection leaves item 7 out with a reason that names draft pull request 7 and the failed `check_proposal`

#### Scenario: A body edit starts a new attempt
- **WHEN** A person edits the text of item 7 after the job recorded a re-stage of its draft
- **THEN** The selection reads the draft of item 7 again and may replace it

## MODIFIED Requirements

### Requirement: The job leaves out the items it must not stage
The job SHALL leave out an item that is not Ready, holds `needs-split`, fails `roadmap-author-trust`, or depends on an open issue. It SHALL leave out a held item, whose branch is on `origin` or in a worktree, unless its one draft fails the plan check with no unresolved thread, no path outside the change folder, and no re-stage is recorded. It SHALL leave out an item whose plan is on `origin/<default branch>` or archived there. The plan SHALL name each item it leaves out and say why.

#### Scenario: Items that are left out
- **WHEN** The filter names a Blocked item, an item with `needs-split`, an item opened by an account with no write access that the jobs do not trust, an item of a bot that no review approved, an item that depends on an open issue, and an item with a pushed branch whose draft plan passes the plan check
- **THEN** The plan stages none of them and gives one reason for each

#### Scenario: A draft plan that fails the check
- **WHEN** Item 7 has one open draft pull request on `origin`, `check_proposal` finds a problem in its change files, no review thread of it is unresolved, and its branch changes only files of the change folder of item 7
- **THEN** The plan stages item 7 again and names draft pull request 7 as the one to replace

#### Scenario: A draft plan that passes, a review thread, and a commit beyond the plan
- **WHEN** Three held items have one draft pull request each: the plan of one passes `check_proposal`, one has an unresolved review thread, and the branch of one changes a path outside its change folder
- **THEN** The plan stages none of them and gives each the reason that names its pushed branch

#### Scenario: The plan is on the default branch and the branch is gone
- **WHEN** `origin/main` holds the folder `openspec/changes/7-stop-the-drop/`, `origin` has no branch for item 7, the record of item 7 names a merged plan pull request, and the title of item 7 gives another slug
- **THEN** The plan stages no item, and the reason for item 7 says that its plan is on `main` and names the folder

#### Scenario: The plan is on the default branch and the branch is still there
- **WHEN** `origin/main` holds the folder of item 7 and `origin` still has the staged branch of item 7
- **THEN** The plan stages no item, and item 7 has one reason

#### Scenario: The change is archived
- **WHEN** `origin/main` holds the folder `openspec/changes/archive/2026-10-28-7-stop-the-drop/`
- **THEN** The plan leaves out item 7 and the reason says that its change is archived on `main`

#### Scenario: The issue is closed
- **WHEN** The folder of item 7 is on `origin/main` and item 7 is closed
- **THEN** The plan holds no reason for item 7, because the job reads open items only

#### Scenario: A stale record and no plan on the default branch
- **WHEN** The record of item 7 names a merged plan pull request and a branch that is gone, and `origin/main` holds no folder for item 7
- **THEN** The plan stages item 7 again

#### Scenario: Two planned items
- **WHEN** `origin/main` holds the folders of items 7 and 8, and both are Ready bugs
- **THEN** The plan leaves out both, each with its own reason
