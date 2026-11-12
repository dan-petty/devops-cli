## Purpose
The CLI reference, `docs/CLI_REFERENCE.md`, is a short generated index of the `devops` command groups and the command matrix, so that a reader, a page fetch and the docs site can use it. The page of each group in `docs/commands/` holds the full text of its commands.

## ADDED Requirements

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
