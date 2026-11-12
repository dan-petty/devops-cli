## ADDED Requirements

### Requirement: A command cited in a sentence ends at the first word that the command tree does not take
The plan check SHALL end a `devops` command that a sentence cites with no code span at the first word that the command tree does not take. The command tree takes an option, the values of a known option, a subcommand name and the declared arguments of the command. Each `uv run devops` of a sentence SHALL start a new command.

#### Scenario: Prose after a command is no argument
- **WHEN** a plan cites `uv run devops ci to confirm the full gate including the constructs row passes` in a sentence with no code span
- **THEN** the check returns no command-resolution problem

#### Scenario: An unknown option in a sentence is refused
- **WHEN** a plan cites `uv run devops gh pages verify --root_dir docs to check the pages` in a sentence with no code span
- **THEN** the check returns a problem that names `--root_dir`

#### Scenario: An unknown option after an argument in a sentence is refused
- **WHEN** a plan cites `uv run devops pr monitor 4982 --bogus to watch it` in a sentence with no code span
- **THEN** the check returns a problem that names `--bogus`

### Requirement: A command cited in a sentence keeps its subcommand and a word before an option
The plan check SHALL keep the next word of a sentence in a cited command when the group before it needs a subcommand. It SHALL keep a word before an option in the cited command, because a sentence puts no option after an English word.

#### Scenario: An unknown subcommand in a sentence is refused
- **WHEN** a plan cites `uv run devops roadmap follow 3076 to see the job` in a sentence with no code span
- **THEN** the check returns a problem that names `follow`

#### Scenario: An unknown subcommand before an option in a sentence is refused
- **WHEN** a plan cites `uv run devops ai ast-graph --help to see the options` in a sentence with no code span
- **THEN** the check returns a problem that names `ast-graph`
