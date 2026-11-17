## ADDED Requirements

### Requirement: A row line shows the name that --only and --skip take

The `devops ci` gate SHALL print each row line with its literal name in square brackets, escaped
so that Rich markup does not consume it. The name SHALL be the same string that `--only` and
`--skip` accept. The completed, skipped, timed-out, cancelled and `python_version` lines SHALL
carry it.

#### Scenario: A completed row shows its name

- **WHEN** a row completes and the gate prints its line
- **THEN** the line holds `[<name>]` and Rich renders the name as literal text

#### Scenario: A skipped row shows its name

- **WHEN** a row is skipped
- **THEN** the line holds `[<name>] skipped: <cause>`

#### Scenario: The printed name selects the row

- **WHEN** a user passes the printed name to `--only`
- **THEN** the gate runs that row and prints the same name again

#### Scenario: A name holds markup characters

- **WHEN** a row name holds brackets
- **THEN** the printed line holds the literal name and reads no part of it as markup
