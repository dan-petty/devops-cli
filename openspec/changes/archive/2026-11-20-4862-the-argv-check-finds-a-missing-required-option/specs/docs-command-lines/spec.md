## Purpose
How `devops docs check` resolves each `devops` command line of the hand-written and prompt documents and of the source against the real command tree without running it, so that an agent that copies a documented command line gets a command that runs.

## ADDED Requirements

### Requirement: A command line that omits a required option is refused
The command resolver SHALL report the defect `missing_required` with the first long name of the option when a `devops` command line gives a token after the command path and gives no value to a required option of that command.

#### Scenario: The summary option is missing
- **WHEN** a test resolves `devops pr describe 1`
- **THEN** the finding has the defect `missing_required`, the command path `devops pr describe` and the token `--summary`

### Requirement: A command line that omits a required argument is refused
The command resolver SHALL report the defect `missing_required` with the name of the argument when a `devops` command line gives a token after the command path and no word fills a required argument, also an argument that takes any number of words.

#### Scenario: The issue argument is missing
- **WHEN** a test resolves `devops pr describe --summary x`
- **THEN** the finding has the defect `missing_required`, the command path `devops pr describe` and the token `issue`

#### Scenario: The targets argument is missing
- **WHEN** a test resolves `devops review benchmark --no-static-scan`
- **THEN** the finding has the defect `missing_required`, the command path `devops review benchmark` and the token `targets`

### Requirement: A bare command mention is not refused
The command resolver MUST NOT report a defect for a command mention that gives no token after the command path, because a sentence can name a command and give no command line.

#### Scenario: A mention with no token
- **WHEN** a test resolves `devops pr describe` with no token after the command path
- **THEN** the resolver returns no finding

### Requirement: A placeholder fills an argument and not an option
The command resolver SHALL count a placeholder, such as `<issue>`, as one word that fills the argument at its position. A placeholder MUST NOT give a value to a required option.

#### Scenario: A placeholder for the issue argument
- **WHEN** a test resolves `devops pr describe <issue>`
- **THEN** the finding has the defect `missing_required` and the token `--summary`, and no finding names `issue`

### Requirement: A required parameter is given as Click parses it
The command resolver SHALL find a missing required parameter with the option parser, `consume_value` and `value_is_missing` of Click, so an option is given in each form that Click takes, also when a placeholder fails conversion before Click reaches the option.

#### Scenario: A short option with an attached value
- **WHEN** a test resolves `devops pr describe <issue> -sx`
- **THEN** the resolver returns no finding

#### Scenario: A long option with an equals value
- **WHEN** a test resolves `devops pr describe <issue> --summary=x`
- **THEN** the resolver returns no finding
