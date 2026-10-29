## MODIFIED Requirements

### Requirement: The job leaves out the items it must not stage
The job SHALL leave out an item that is not Ready, has the label `needs-split`, has an untrusted author, or depends on an open issue. It SHALL leave out a held item: `origin` or a worktree of the clone has a branch `<type>/<issue>-<slug>` for it. It SHALL leave out an item whose plan is on `origin/<default branch>` or whose change is archived there, matched by the issue number only. The plan SHALL name each item it leaves out and say why.

#### Scenario: Items that are left out
- **WHEN** the filter names a Blocked item, an item with `needs-split`, an item opened by an account with no write access, an item that depends on an open issue, and an item with a pushed branch
- **THEN** the plan stages none of them and gives one reason for each

#### Scenario: The plan is on the default branch and the branch is gone
- **WHEN** `origin/main` holds the folder `openspec/changes/7-stop-the-drop/`, `origin` has no branch for item 7, the record of item 7 holds a `stage.pr` that is merged, and the title of item 7 gives another slug
- **THEN** the plan stages no item, and the reason for item 7 says that its plan is on `main` and names the folder

#### Scenario: The plan is on the default branch and the branch is still there
- **WHEN** `origin/main` holds the folder of item 7 and `origin` still has the staged branch of item 7
- **THEN** the plan stages no item, and item 7 has one reason

#### Scenario: The change is archived
- **WHEN** `origin/main` holds the folder `openspec/changes/archive/2026-10-28-7-stop-the-drop/`
- **THEN** the plan leaves out item 7 and the reason says that its change is archived on `main`

#### Scenario: The issue is closed
- **WHEN** the folder of item 7 is on `origin/main` and item 7 is closed
- **THEN** the plan holds no reason for item 7, because the job reads open items only

#### Scenario: A stale record and no plan on the default branch
- **WHEN** the record of item 7 names a merged `stage.pr` and a branch that is gone, and `origin/main` holds no folder for item 7
- **THEN** the plan stages item 7 again

#### Scenario: Two planned items
- **WHEN** `origin/main` holds the folders of items 7 and 8, and both are Ready bugs
- **THEN** the plan leaves out both, each with its own reason

### Requirement: A staged item gets a draft pull request
The job SHALL open a draft pull request whose title is `docs(openspec): plan #<issue> <summary>` and whose body starts with `Plans #<issue>` and holds no closing keyword. The part of the title after the colon SHALL have at most 60 characters. The job SHALL NOT mark the pull request ready.

#### Scenario: The draft opens
- **WHEN** the job stages a Ready bug
- **THEN** a draft pull request opens with a body that starts with `Plans #<issue>`

#### Scenario: The body names no closing keyword
- **WHEN** the plan of the model holds the text `Closes #12` in its description of the change
- **THEN** the job stops that item with a failure that names the closing keyword, and pushes nothing

#### Scenario: The title of a bug and of a feature
- **WHEN** the job stages item 12, a bug, and item 13, a feature
- **THEN** the title of each draft starts with `docs(openspec): plan #12 ` and `docs(openspec): plan #13 `, and the branch of each keeps the type of its issue

#### Scenario: A long summary
- **WHEN** the model gives a summary of 60 characters for item 2656
- **THEN** the title after the colon has at most 60 characters, and the summary is cut at a word

## ADDED Requirements

### Requirement: A round reads the plans on the default branch once
A round SHALL fetch the default branch and read the tree of `origin/<default branch>` with one `git ls-tree` of `openspec/changes/` and `openspec/changes/archive/`, before it selects an item. A read that fails SHALL fail the run with the reason of git and stage no item.

#### Scenario: One read for many items
- **WHEN** a round judges three items
- **THEN** git received one `ls-tree` command

#### Scenario: The tree cannot be read
- **WHEN** `git ls-tree` fails
- **THEN** the run raises an error that names the command and the reason of git, and no item is staged
