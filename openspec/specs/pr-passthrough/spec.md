# pr-passthrough Specification

## Purpose

Forward `gh` pass-through flags (`--json`, `--jq`, `--comments`, `--search`, `--head`, `--base`) and `pr status` across `devops pr` and `devops gh pr` with raw-output mode and dry-run request plans.

## Requirements

### Requirement: PR view forwards JSON, jq, and comments options
`devops pr view` and `devops gh pr view` SHALL forward `--json <fields>`, `--jq`/`-q <expr>`, `--comments`/`-c`, and `--repo`/`-R` to `gh pr view`. When `--json` or `--jq` is set and `gh` exits non-zero, the command SHALL print the error and exit with `gh`'s exit code without invoking REST fallback rendering.

#### Scenario: PR view forwards JSON, jq, and comments
- **WHEN** a test invokes `devops pr view 12 --json number,title --jq .title --comments` with a `gh` process stub
- **THEN** the stub receives `gh pr view 12 --comments --json number,title --jq .title` and stdout prints the stub output

#### Scenario: GH path forwards PR view JSON
- **WHEN** a test invokes `devops gh pr view 12 --json title` with a `gh` process stub
- **THEN** the stub receives `gh pr view 12 --json title` and prints its output

### Requirement: PR list forwards JSON, jq, search, head, and base options
`devops pr list` and `devops gh pr list` SHALL forward `--search`/`-S`, `--head`/`-H`, `--base`/`-B`, `--json`, and `--jq`/`-q` to `gh pr list`. When `--json` or `--jq` is omitted, the command SHALL render the PR table; when `--json` or `--jq` is set, the command SHALL print raw `gh` stdout on success and print `gh` error with `gh`'s exit code and no table on failure.

#### Scenario: PR list forwards head and JSON raw output
- **WHEN** a test invokes `devops pr list --head feature --json number` with a `gh` stub returning a JSON array
- **THEN** the stub receives `--head feature` and `--json number`, and stdout prints the raw JSON array without table formatting

#### Scenario: PR list forwards search and base in table mode
- **WHEN** a test invokes `devops pr list --search is:draft --base main` with a `gh` stub returning PR JSON
- **THEN** the stub receives `--search is:draft` and `--base main` alongside default JSON fields and renders the formatted PR table

#### Scenario: Raw output failure prints gh error and no table
- **WHEN** a test invokes `devops pr list --json number` and `gh` exits 1 with a rate-limit error
- **THEN** the command prints `gh`'s error, exits 1, and invokes no table fallback

### Requirement: PR status command runs gh pr status
`devops pr status` and `devops gh pr status` SHALL invoke `gh pr status` forwarding optional `--json`, `--jq`/`-q`, and `--repo`/`-R`, and declare `@dry_run_class("request-plan")`.

#### Scenario: PR status forwards JSON and repo
- **WHEN** a test invokes `devops pr status --json number --repo owner/repo` with a `gh` stub
- **THEN** the stub receives `gh pr status --json number --repo owner/repo` and prints the output with exit code 0

### Requirement: Dry run prints planned gh arguments
`devops pr view`, `devops pr list`, and `devops pr status` under `--dry-run` SHALL include all forwarded options in the planned `gh` argv and execute zero subprocesses.

#### Scenario: Dry run prints planned argv for new flags and status
- **WHEN** tests run `devops pr view 12 --json title --dry-run`, `devops pr list --head feat --search is:draft --dry-run`, and `devops pr status --json number --dry-run`
- **THEN** each output prints the planned `gh` argv holding those flags and executes zero external processes
