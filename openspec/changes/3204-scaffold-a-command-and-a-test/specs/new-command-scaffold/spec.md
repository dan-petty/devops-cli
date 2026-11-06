## Purpose
How `devops new command` and `devops new test` write the files of a new command or test in project form, refuse to write over a file, and print the steps that only a person can finish.

## ADDED Requirements

### Requirement: The new group lists the command and test subcommands
The `devops new` command group SHALL list the `command` and `test` subcommands.

#### Scenario: Help lists both subcommands
- **WHEN** A user runs `devops new --help`.
- **THEN** The output names `command` and `test`.

### Requirement: The command scaffold writes the command module and the language entries
`devops new command <group> <name>` SHALL write the command function in the group module and its help and message entries in `lang/en/`.

#### Scenario: The command function and the language entries are written
- **WHEN** A user runs `devops new command sample hello` in a temporary repository whose `sample` group exists.
- **THEN** The `sample` group module holds the `hello` function, and `lang/en/` holds its help and message entries.

#### Scenario: An unknown group is refused
- **WHEN** A user runs `devops new command missing hello` and no `missing` group module exists.
- **THEN** The command exits nonzero, names the group module it looked for, and writes no file.

### Requirement: The command scaffold writes the test at the mirror path
`devops new command` SHALL write a test module in the mirror folder of the group module, named `test_<group>_<command>.py`, holding a failing first test and `match=` in its error check.

#### Scenario: The command test sits at the mirror path and uses match
- **WHEN** A user runs `devops new command sample hello`.
- **THEN** The test module `tests/commands/test_sample_hello.py` sits in the mirror folder of the `sample` module and holds a failing first test and `pytest.raises` with `match=`.

### Requirement: The help that the scaffold writes is short and names its page
The help entry that the scaffold writes SHALL hold at most three sentences and SHALL name the documentation page of its command.

#### Scenario: The generated help obeys the guard
- **WHEN** The scaffold writes the help of a command.
- **THEN** The help holds at most three sentences and names the page of its command.

### Requirement: The scaffold prints the steps that remain manual
The command scaffold SHALL print each step that it cannot do, and that list SHALL name `devops docs generate --sync-readme`.

#### Scenario: The checklist names the regeneration command
- **WHEN** A user runs `devops new command sample hello`.
- **THEN** The output holds `devops docs generate --sync-readme` and names no list that the change derives.

### Requirement: The test scaffold writes the test at the mirror path
`devops new test <module>` SHALL write the test module at the mirror path of the source module.

#### Scenario: The mirror path is used
- **WHEN** A user runs `devops new test src/devops_cli/config/constants.py`.
- **THEN** The scaffold writes the test module at the mirror path of that source module.

### Requirement: The test scaffold refuses a path that is not a source module
`devops new test` SHALL refuse a path outside `src/devops_cli` and SHALL name the mirror path that the rule requires.

#### Scenario: A flat test path is refused
- **WHEN** A user runs `devops new test` on a test path that is not the mirror path of a source module.
- **THEN** The command exits nonzero and names the required mirror path.

### Requirement: The test that the scaffold writes asks for the fake of its edge
The test module that the scaffold writes SHALL ask for the shared fake fixture of each edge that its source module reaches.

#### Scenario: The generated test asks for the GitHub fake
- **WHEN** A user runs the scaffold for a source module that reads GitHub.
- **THEN** The test asks for the `github_api` fixture.

### Requirement: The scaffold refuses to write over a file
The scaffold SHALL write no file when any target path exists, SHALL name each existing path, and SHALL exit nonzero.

#### Scenario: An existing target is refused
- **WHEN** A user runs the same scaffold command twice.
- **THEN** The second run exits nonzero, names the existing path, and leaves the file as it was.

### Requirement: A dry run writes nothing
`--dry-run` SHALL print every target path and SHALL write no file.

#### Scenario: The dry run lists the target paths
- **WHEN** A user runs `devops new command sample hello --dry-run`.
- **THEN** The output lists the group module, the language entry and the test module, and no file changes on disk.

### Requirement: A skill names both scaffold commands
A skill document under each of `.claude/skills/` and `.agents/skills/` SHALL name `devops new command` and `devops new test`.

#### Scenario: The skill names both commands
- **WHEN** A test reads the skill documents of `.claude/skills/` and of `.agents/skills/`.
- **THEN** The skill of each root names `devops new command` and `devops new test`, and the two skills hold the same text.
