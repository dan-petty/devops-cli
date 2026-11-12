## MODIFIED Requirements

### Requirement: The command prints the whole issue
`devops gh issue view <number>` SHALL read the issue `<number>` of the repository with one request to `GET /repos/{repo}/issues/{number}`. It SHALL print the number, title, state, web URL, milestone, labels, assignees, created date and updated date, an empty line, and the full body. It SHALL NOT cut the title or the body. `--repo` and `-R` SHALL name the repository, and the default SHALL be the origin of the checkout.

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
