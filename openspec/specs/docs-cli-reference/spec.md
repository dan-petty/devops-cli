# docs-cli-reference Specification

## Purpose
The CLI reference, `docs/CLI_REFERENCE.md`, is a short generated index of the `devops` command groups and the command matrix, so that a reader, a page fetch and the docs site can use it. The page of each group in `docs/commands/` holds the full text of its commands.

## Requirements

### Requirement: The CLI reference is an index of the command group pages
`devops docs generate` SHALL write `docs/CLI_REFERENCE.md` with one row for each command group, which holds the group, a link to `commands/<group>.md` and the one-line help of the group, and with the command matrix, which holds one row for each command with its usage and its summary. The CLI reference SHALL hold no usage block and no table of arguments or options. The page of each group SHALL hold them, and the description of the group when it is not the summary.

#### Scenario: A group with one command
- **WHEN** the generator renders the CLI reference of the group `dummy`, whose summary is `Dummy summary`, with the command `devops dummy run [OPTIONS]`, whose summary is `Run dummy` and which has the flag `--flag`
- **THEN** the page holds one group row that links `commands/dummy.md` with the text `Dummy summary`, and one matrix row that links `commands/dummy.md` with the usage `devops dummy run [OPTIONS]` and the text `Run dummy`, and it holds no code block and no `--flag`

#### Scenario: The page of a group holds the description of the group
- **WHEN** the generator renders the page of the group `dummy`, whose description is `Dummy long description`
- **THEN** the page holds `Dummy long description` after the summary and before the commands

### Requirement: README.md holds no generated block
`README.md` SHALL link `docs/CLI_REFERENCE.md` and SHALL hold no command matrix. `devops docs` SHALL have no command and no option that writes or checks a block of `README.md`.

#### Scenario: devops docs has no README sync
- **WHEN** a test reads the command tree of `devops docs`
- **THEN** no command name and no option name holds `readme`

#### Scenario: The README links the CLI reference
- **WHEN** a test reads `README.md`
- **THEN** it holds a link to `docs/CLI_REFERENCE.md`, no command matrix marker and no command matrix table

### Requirement: The CLI reference tab of the docs site opens on the index
The `CLI reference` tab of `.nav.yml` SHALL list `docs/CLI_REFERENCE.md` as its first page, with the title `Index`, and then the pages of `docs/commands/`.

#### Scenario: The nav of the CLI reference tab
- **WHEN** a test reads `.nav.yml`
- **THEN** the `CLI reference` tab is the index page `docs/CLI_REFERENCE.md` and then the glob `docs/commands/*.md`

### Requirement: Generated documents carry the linguist-generated attribute

`.gitattributes` SHALL set `linguist-generated=true` for every glob of the generated class of `CONST_DOCS_INVENTORY`, and tracked Markdown files outside that class (except `CHANGELOG.md`, already marked generated for `release-please`) MUST remain `unspecified`. A missing glob line in `.gitattributes` MUST fail the attribute check and name both the glob and the missing attribute.

#### Scenario: Generated and hand-written attributes match inventory

- **WHEN** `git check-attr linguist-generated` checks every tracked Markdown file
- **THEN** each file matching `CONST_DOCS_INVENTORY["generated"]` prints `true` and every non-generated, non-`CHANGELOG.md` tracked Markdown file (including `README.md`) prints `unspecified`

#### Scenario: Missing generated glob fails attribute check

- **WHEN** a glob is added to `CONST_DOCS_INVENTORY["generated"]` without a line in `.gitattributes`
- **THEN** the attribute check fails and names the missing glob and `linguist-generated=true`

### Requirement: Review skip reads the generated class from inventory

`is_secret_scan_only` SHALL return `True` for every path matching `CONST_DOCS_INVENTORY["generated"]`, and `CONST_REVIEW_ROUTED_PATH_PATTERNS` MUST NOT contain `docs/commands/*.md`, `docs/CLI_REFERENCE.md`, or any generated glob.

#### Scenario: Dynamically added generated glob is skipped by review

- **WHEN** a glob is added to `CONST_DOCS_INVENTORY["generated"]` and passed to `is_secret_scan_only`
- **THEN** `is_secret_scan_only` returns `True`

### Requirement: CONTRIBUTING.md documents the generated-file rebase conflict step

The Documentation Synchronization bullet of `CONTRIBUTING.md` SHALL document running `git checkout --ours -- <file>`, `git rebase --continue`, and `uv run devops docs generate`.

#### Scenario: Conflict procedure appears beside docs generation

- **WHEN** a contributor reads the Documentation Synchronization bullet in `CONTRIBUTING.md`
- **THEN** it names `git checkout --ours -- <file>`, `git rebase --continue`, and `uv run devops docs generate`
