# roadmap-stage/scaffold Specification

## Purpose
How the scaffold step creates, resumes, adopts or holds the item branch for roadmap stage runs, and keeps App-only branches from being deleted.

## Requirements

### Requirement: Create the item branch with no commit
The scaffold step SHALL create the item branch ref at the head of `origin/main` and add no commit when no branch names the item.

#### Scenario: No branch names the item
- **WHEN** the item has no branch on origin and the record holds no branch
- **THEN** the step creates one ref at the head of `origin/main`, writes `scaffold.branch` and writes the result `created`

### Requirement: The plain branch form with the change-folder slug
The scaffold step SHALL name the branch `<type>/<issue>-<slug>` with the slug of the change folder and no `-<i>` suffix.

#### Scenario: One candidate makes the branch
- **WHEN** `roadmap.<job>.candidates` is 1 and the change folder is `add-the-widget`
- **THEN** the branch name is `<type>/<issue>-add-the-widget`, built by `branch_form.branch_name`, and `branch_form.py`, `parse_branch` and `worktree_add.py` are unchanged

### Requirement: Resume on an App-only branch that the record names
The scaffold step SHALL resume on a branch that names the item when only the App wrote to it past `origin/main` and the record names that branch.

#### Scenario: The record names an App-only branch
- **WHEN** a branch names the item, each commit past `origin/main` has the App author, and the record holds that branch
- **THEN** the step writes the result `resumed`, keeps `scaffold.branch` and creates no ref

### Requirement: Adopt an App-only branch that the record does not name
The scaffold step SHALL adopt an App-only branch that names the item when the record holds no branch, and write that branch to `scaffold.branch`.

#### Scenario: An App-only branch with no record entry
- **WHEN** an App-only branch names the item and the record holds no `scaffold.branch`
- **THEN** the step writes the result `adopted` and records the branch name in `scaffold.branch`

### Requirement: Hold a branch that a person or an agent wrote
The scaffold step SHALL write the result `held` and change nothing when the branch holds a commit of a person or an agent past `origin/main`.

#### Scenario: The branch holds a commit of a person
- **WHEN** the branch holds a commit past `origin/main` whose author is not the App
- **THEN** the step writes the result `held` with the holder, writes no record key and makes no git or GitHub write

### Requirement: One result line with the four results
The scaffold step MUST write one JSON result line with `job=scaffold` and one result of `created`, `resumed`, `adopted` or `held`.

#### Scenario: A held branch ends the run
- **WHEN** the step ends with the result `held`
- **THEN** the line holds `job=scaffold` and `result=held`, and the step exits 0

### Requirement: A dry run sends no request
The scaffold step MUST send no request to GitHub or git when it runs with `--dry-run`.

#### Scenario: A dry run on an item with no branch
- **WHEN** the step runs with `--dry-run`
- **THEN** the fake GitHub client counts zero requests, the step writes no record key and the step creates no ref

### Requirement: Only the scaffold module creates the plan branch ref
No module of the roadmap stage SHALL create the plan branch ref other than `src/devops_cli/roadmap/steps/scaffold.py`.

#### Scenario: The structural test reads the stage modules
- **WHEN** the test reads each module under `src/devops_cli/roadmap/stage/` and `src/devops_cli/roadmap/steps/`
- **THEN** no module other than `steps/scaffold.py` calls the client method that posts to `POST /repos/{owner}/{repo}/git/refs`

### Requirement: The orphan cleanup keeps an App-only branch of a Ready item
The stage job MUST NOT delete an App-only branch of a Ready item when it judges a `stage.pending` mark.

#### Scenario: An orphan mark on a Ready item with an App-only branch
- **WHEN** a Ready item holds a `stage.pending` mark older than 1 hour and its branch holds only App commits
- **THEN** the job makes no delete of the branch

### Requirement: The documents state the resume rule
`docs/roadmap/stage.md` and `docs/ROADMAP_WORKFLOW.md` SHALL state the resume rule of the scaffold step.

#### Scenario: A test reads the two documents
- **WHEN** the test reads `docs/roadmap/stage.md` and `docs/ROADMAP_WORKFLOW.md`
- **THEN** each document names the four results `created`, `resumed`, `adopted` and `held`, and `docs/ROADMAP_WORKFLOW.md` lists the record key `scaffold.branch`
