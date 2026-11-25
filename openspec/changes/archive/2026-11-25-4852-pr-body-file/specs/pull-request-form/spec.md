## ADDED Requirements

### Requirement: PR create and edit read body text from --body-file or stdin
`devops pr create` and `devops pr edit` SHALL accept `--body-file` / `-F` (`typer.FileText`) to read the pull request body as UTF-8 text from a file path or from standard input when `-` is given, and pass that text to `gh` via `--body`.

#### Scenario: Dry run reads file body for pr create and pr edit
- **WHEN** `devops pr create --title 'feat(pr): x' --body-file body.md --dry-run` or `devops pr edit 12 --body-file body.md --dry-run` runs
- **THEN** the planned `gh` argv carries `--body` with the file's text and sends 0 requests

#### Scenario: Standard input body via dash
- **WHEN** `devops pr create --title 'feat(pr): x' --body-file - --dry-run` or `devops pr edit 12 --body-file - --dry-run` reads text from standard input
- **THEN** the planned `gh` argv carries `--body` with that standard input text

### Requirement: --body and --body-file are mutually exclusive and missing files fail with exit code 2
`devops pr create` and `devops pr edit` MUST refuse `--body` together with `--body-file` by exiting with code 2 and naming both options, and MUST exit with code 2 naming `--body-file` without printing file text when the path does not exist.

#### Scenario: Both body flags specified
- **WHEN** `--body x` and `--body-file f` are both passed
- **THEN** the command exits 2 and names both `--body` and `--body-file`

#### Scenario: Missing body file path
- **WHEN** `--body-file missing.md` names a file that does not exist
- **THEN** the command exits 2 and names `--body-file`

### Requirement: PR create form checks apply to file bodies
`devops pr create` MUST apply its 1,000-character body limit and template-text refusal to text read from `--body-file`.

#### Scenario: Oversized file body is refused
- **WHEN** `--body-file` points to a body whose prose exceeds 1,000 characters
- **THEN** `devops pr create` exits 1 with the form refusal and sends no `gh` request
