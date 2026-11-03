# Spec Delta

## MODIFIED Requirements

### Requirement: A verification command has a limit and a reason that is safe to show
The words of a verification command of any program SHALL hold at most 2000 characters in all, and no word SHALL hold a NUL byte or a character that does not encode to UTF-8. A word, a command and the output of a command that a reason names SHALL be escaped and cut, so that the reason holds no raw control character, no line or paragraph separator and no bidi override. The stop reason SHALL show the command cut to 2000 characters.

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

#### Scenario: The output of a command
- **WHEN** a verification command fails, or a negative search finds a line, and the output holds ESC, U+202E and NEL
- **THEN** the reason shows the output with the escapes `\x1b`, `\u202e` and `\x85`, and holds none of the raw characters

#### Scenario: A word that cannot be an argument
- **WHEN** a Verification line names `grep a` followed by a NUL byte, or a word with a lone surrogate
- **THEN** the step stops with the reason that a word holds a NUL byte or a character that cannot be encoded, starts no process, and raises no error
