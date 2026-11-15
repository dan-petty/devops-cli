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
