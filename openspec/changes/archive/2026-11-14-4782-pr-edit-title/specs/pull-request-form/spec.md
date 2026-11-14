## ADDED Requirements

### Requirement: devops pr edit refuses a title that the title check refuses
`devops pr edit --title` SHALL run `title_problems` on the title and SHALL refuse the edit with the message of `devops pr create` when it returns a problem, before it sends the edit.

#### Scenario: A title with a breaking marker
- **WHEN** the user runs `devops pr edit 184 --title "fix(pr)!: add the check"`
- **THEN** the command exits 1, prints the problem about `!`, and sends no edit

#### Scenario: A long summary
- **WHEN** the title summary holds 70 characters
- **THEN** the command exits 1 and prints the summary limit

#### Scenario: A valid title
- **WHEN** the title passes `title_problems`
- **THEN** the command sends the edit
