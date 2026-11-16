# roadmap-stage/open Specification

## ADDED Requirements

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
