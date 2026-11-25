# roadmap-stage/open Specification

## Purpose
How the open step creates, updates, and recovers draft pull requests for roadmap jobs, and keeps pull request creation unified and idempotent.

## Requirements

### Requirement: Open a draft pull request
The open step SHALL open a draft pull request when no open pull request exists for the head branch into the base branch.

#### Scenario: Open a new draft pull request
- **WHEN** no open pull request exists for the head branch into the base branch
- **THEN** the step opens one draft pull request and returns the result `created`

### Requirement: Update an existing pull request
The open step SHALL update an existing open pull request for the head branch and base branch and change only the fields that differ.

#### Scenario: Update when title or body differs
- **WHEN** an open pull request exists and its title or body differs from the request
- **THEN** the step updates the pull request and returns the result `updated`

#### Scenario: No update when fields are equal
- **WHEN** an open pull request exists and all fields match the request
- **THEN** the step sends no update request and returns the result `unchanged`

### Requirement: One retry on refused text
The open step SHALL retry with form-checked text once when GitHub refuses the pull request text.

#### Scenario: GitHub refuses text on first attempt
- **WHEN** GitHub refuses the draft pull request creation
- **THEN** the step retries the creation once with form-checked text

### Requirement: Set status to in progress for delivery
The open step SHALL set the status of the item to In Progress through the status writer when opening a delivery pull request.

#### Scenario: Set status for delivery
- **WHEN** the step opens a delivery pull request for a roadmap item
- **THEN** the step writes the In Progress status through `write_status`

### Requirement: Record pull request marks
The open step SHALL record `<kind>.pr` in the item record.

#### Scenario: Record mark on creation
- **WHEN** the step opens a pull request for kind `plan` or `delivery`
- **THEN** the step writes `stage.pr` or `implement.pr` to the item record

### Requirement: Upsert marked comment
The open step SHALL upsert a marked comment on the pull request when comment text is provided.

#### Scenario: Upsert comment
- **WHEN** the request provides comment text with a marker
- **THEN** the step updates an existing marked comment or creates a new comment

### Requirement: Dry run sends no request
The open step SHALL send zero requests to GitHub when running with `--dry-run`.

#### Scenario: Dry run
- **WHEN** the step runs with `--dry-run`
- **THEN** the step sends no requests to GitHub and returns the planned result

### Requirement: Refuse second open pull request
The open step SHALL refuse to open a second pull request for an item when an open pull request already exists on another branch.

#### Scenario: Second open pull request refused
- **WHEN** an open pull request already exists for the item on a different branch
- **THEN** the step refuses the request and creates no pull request

### Requirement: Refuse commit with skip ci marker
The open step SHALL refuse to open a pull request when the head commit message contains `[skip ci]`.

#### Scenario: Head commit message contains skip ci
- **WHEN** the head commit message contains `[skip ci]`
- **THEN** the step refuses the request and creates no pull request

### Requirement: Recovery of pull request
The open step SHALL be due to recover a pull request when the branch head equals `checked_sha` in the item record and no open pull request exists.

#### Scenario: Recover pull request
- **WHEN** the branch head equals `checked_sha` in the record and no open pull request exists for that head and base
- **THEN** the step recovers and opens the pull request in at most 3 requests

### Requirement: A type that ships runtime code
The open step SHALL write a type that release-please shows when the diff of the head changes runtime code under a type that `release-please-config.json` hides: `feat` when the diff adds a runtime file, else `fix`. It SHALL use the rule of the `Semantic PR title` check.

#### Scenario: A test item changes runtime code
- **WHEN** the title has the type `test` and the diff of the head changes a file under `src/devops_cli/`
- **THEN** the step writes the title with the type `fix`, and the CI title rules accept the title

#### Scenario: A test item adds a runtime module
- **WHEN** the title has the type `test` and the diff of the head adds a file under `src/devops_cli/`
- **THEN** the step writes the title with the type `feat`

#### Scenario: A shown type
- **WHEN** release-please shows the type of the title
- **THEN** the step keeps the type and reads no diff

### Requirement: Check the title and the body before the write
The open step SHALL remove a scope that `.github/labels.yml` does not declare, and SHALL refuse a title that `title_problems` refuses. It SHALL refuse a plan body that `plan_body_problems` refuses, and a delivery body that closes no issue, another issue, or more than one issue. A refusal SHALL name every problem, and the step SHALL write nothing.

#### Scenario: An undeclared scope
- **WHEN** the title has a scope with no label in `.github/labels.yml`
- **THEN** the step writes the title with no scope

#### Scenario: A long summary
- **WHEN** the summary of the title has more than 60 characters
- **THEN** the step refuses the request and creates no pull request

#### Scenario: A plan body that closes an issue
- **WHEN** a plan body holds a closing keyword
- **THEN** the step refuses the request and creates no pull request

### Requirement: The open row
The Service SHALL have a row `open` with the modes `off`, `plan` and `on` in `roadmap.open.mode`, which starts in `plan`. The row SHALL take the pushed branch that `implement.branch` of an open item names when no open pull request holds the item, no Job, orphan mark or stop holds it, and GitHub associates no pull request with its head. Mode `on` SHALL run the open step for it.

#### Scenario: Mode plan
- **WHEN** the mode is `plan` and a candidate branch exists
- **THEN** the row logs the branch and writes nothing to GitHub

#### Scenario: Mode on
- **WHEN** the mode is `on` and a candidate branch changes runtime code for an item of the type `test`
- **THEN** the row opens a draft pull request whose type ships a release and whose body closes the item

#### Scenario: A closed head
- **WHEN** GitHub associates a closed pull request with the head of the branch
- **THEN** the row does not open the branch

### Requirement: Open step requests non-author reviewers on new automated pull requests
When `open_or_update` creates a new draft pull request with `reviewers`, it SHALL exclude the pull request author and already-requested logins case-insensitively and request remaining reviewers via GitHub REST. Automated roadmap callers (`open_row`, `stage`, `implement`, and `roadmap step open`) SHALL pass the repository owner, and dry-run plans SHALL list that write.

#### Scenario: Bot opens a draft pull request
- **WHEN** `open_or_update` creates pull request 701 authored by `devops-cli-service[bot]` with `reviewers=("dan-petty",)` and no prior requested reviewers
- **THEN** the client sends `POST /repos/<repo>/pulls/701/requested_reviewers` with `{"reviewers": ["dan-petty"]}`

#### Scenario: Author matches reviewer or reviewer already requested
- **WHEN** `open_or_update` creates a draft pull request authored by `dan-petty` or already listing `dan-petty` in `requested_reviewers` with `reviewers=("dan-petty",)`
- **THEN** the step sends zero `requested_reviewers` requests

#### Scenario: Automated roadmap dry-run plans list reviewer requests
- **WHEN** `stage_requests` or `implement_requests` builds a dry-run write plan
- **THEN** the plan includes `POST https://api.github.com/repos/<owner>/<name>/pulls/<pull request>/requested_reviewers`
