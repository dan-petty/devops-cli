# gh-issues-view Specification

## Purpose
How `devops gh issues view` reads one issue of a repository through the GitHub session and prints all of it as plain text, and how it refuses a number that names no issue or names a pull request.

## Requirements

### Requirement: The command prints the whole issue
`devops gh issues view <number>` SHALL read the issue `<number>` of the repository with one request to `GET /repos/{repo}/issues/{number}`. It SHALL print the number, title, state, web URL, milestone, labels, assignees, created date and updated date, an empty line, and the full body. It SHALL NOT cut the title or the body. `--repo` and `-R` SHALL name the repository, and the default SHALL be the origin of the checkout.

#### Scenario: An issue that exists
- **WHEN** the user runs `view 9999 -R octo/repo` and the issue has a title of more than 50 characters, a milestone, two labels, one assignee and a body of several lines
- **THEN** the command exits 0
- **AND** the output holds the whole title, the state, the milestone, both labels, the assignee, the web URL (not the API address) and every line of the body

#### Scenario: Fields that are empty
- **WHEN** the issue has no milestone, no label, no assignee and no body
- **THEN** the command exits 0 and the output shows a dash for each empty field

#### Scenario: Markup in the text
- **WHEN** the title is `fix [bold]x[/bold]`
- **THEN** the output holds `fix [bold]x[/bold]` as written

### Requirement: An issue that does not exist is an error
The command SHALL exit with status 1 and print an error that names the number and the repository when GitHub answers 404. It SHALL NOT print an empty issue.

#### Scenario: Missing issue
- **WHEN** the user runs `view 9999 -R octo/repo` and GitHub answers 404
- **THEN** the command exits 1 and the error holds `octo/repo` and `9999`

#### Scenario: GitHub gives no readable answer
- **WHEN** GitHub answers with a 5xx that outlasts the retries
- **THEN** the command exits 1 and prints the error, and no issue

### Requirement: A pull request is not an issue
The command SHALL exit with status 1 and name `devops pr view <number>` when the answer for the number is a pull request.

#### Scenario: A pull request number
- **WHEN** the user runs `view 12 -R octo/repo` and the answer has a `pull_request` key
- **THEN** the command exits 1 and the error holds `devops pr view 12`
