# Spec Delta

## RENAMED Requirements

- FROM: `### Requirement: A negative search has a limit and a reason that is safe to show`
- TO: `### Requirement: A verification command has a limit and a reason that is safe to show`

## MODIFIED Requirements

### Requirement: A verification command has a limit and a reason that is safe to show
The words of a verification command of any program SHALL hold at most 2000 characters in all. A word or a command that a reason names SHALL be escaped and cut, so that the reason holds no raw control character, no line or paragraph separator and no bidi override. The stop reason SHALL show the command cut to 2000 characters.

#### Scenario: A search that is too long
- **WHEN** a Verification line names `! git grep -n` followed by a literal of 300000 characters and `src/`
- **THEN** the step stops with the reason that the command is longer than 2000 characters, shows the command cut to 2000 characters, and starts no process

#### Scenario: A word with a control character
- **WHEN** a Verification line names `! git grep -n` followed by a quoted literal that holds a NUL byte or a line break
- **THEN** the reason shows the word with the escapes `\x00` or `\n`, and holds no NUL byte and no line break

#### Scenario: A command of another program that is too long
- **WHEN** a Verification line names `grep -n zz` or `uv run devops ci test` followed by a word of 300000 characters
- **THEN** the step stops with the reason that the command is longer than 2000 characters, and starts no process

#### Scenario: A command with a control character in the outcome of a step
- **WHEN** a Verification line of a `tasks.md` names `curl` followed by ESC, a right-to-left override (U+202E) and `@octocat`
- **THEN** `outcome.reason` of the step shows the command with the escapes `\x1b` and `\u202e`, and holds no control, format, line separator or paragraph separator character

## ADDED Requirements

### Requirement: The log names no word after a bang
The log line of a shell call whose first word is `!` SHALL name the program `other` and SHALL show no word after it.

#### Scenario: A bang command
- **WHEN** the agent calls the shell with `! Authorization: Bearer abcdef0123456789abcdef`
- **THEN** the log line says `program other`, and holds no word of the command
