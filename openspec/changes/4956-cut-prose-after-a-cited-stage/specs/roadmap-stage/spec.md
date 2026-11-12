## ADDED Requirements

### Requirement: A command cited in a sentence ends at the first word that the command tree does not list
The plan check SHALL end a `devops` command that a sentence cites with no code span at the first word that is no option and no subcommand name of the command tree. A group that needs a subcommand SHALL keep that word as its subcommand. Each `uv run devops` of a sentence SHALL start a new command.

#### Scenario: Prose after a command is no argument
- **WHEN** a plan cites `uv run devops ci to confirm the full gate including the constructs row passes` in a sentence with no code span
- **THEN** the check returns no command-resolution problem

#### Scenario: An unknown option in a sentence is refused
- **WHEN** a plan cites `uv run devops gh pages verify --root_dir docs to check the pages` in a sentence with no code span
- **THEN** the check returns a problem that names `--root_dir`

#### Scenario: An unknown subcommand in a sentence is refused
- **WHEN** a plan cites `uv run devops roadmap follow 3076 to see the job` in a sentence with no code span
- **THEN** the check returns a problem that names `follow`
