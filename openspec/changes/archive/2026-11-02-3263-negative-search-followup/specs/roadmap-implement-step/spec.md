# Spec Delta

## MODIFIED Requirements

### Requirement: A negative search is a verification command in a fixed shape
The step SHALL run a verification command that starts with `!` only as `! git grep [options] <literal> [--] <path>...`, with at least one path and with the options `-n -I -F -i -w -l -c -q` in words of those letters. The step SHALL start no process for a command outside the shape, and the reason of the stop SHALL say which rule of the shape the command breaks.

#### Scenario: A command that is not the fixed shape
- **WHEN** a Verification line names `! rm -rf src/`, `! git grep -n name src/ | cat`, `! git grep -n name src/ ; ls`, `! git grep -n name src/ && ls`, `! git grep -n name src/ > out.txt`, `! git grep -n '$(id)' src/`, `! git grep -O name src/`, `! git grep --no-index -n name src/`, `! git grep -f patterns.txt src/`, `! git grep --open-files-in-pager=cat name src/`, `! git grep -n name /etc` or `! git grep -n name ../other`
- **THEN** the step stops with the reason that says which rule of the shape the command breaks, and starts no process

#### Scenario: A letter outside ASCII
- **WHEN** a Verification line names a literal with a fullwidth `ｆ` or an accented `é`, or a path with one
- **THEN** the step stops with the reason that the text is not a literal, or that the word is not a path, and starts no process

### Requirement: A negative search passes when git finds no match
The step SHALL run a negative search as `git grep` with the options, the literal, `--` and the paths, with no shell. The search SHALL pass when git exits 1, also when a path matches no file. It SHALL stop the step with the matching lines when git exits 0, and with the status when git exits with any other status.

#### Scenario: A name that is gone
- **WHEN** a Verification line names `! git grep -n absent_name src/ tests/` and no file holds `absent_name`
- **THEN** the step runs `git grep -n absent_name -- src/ tests/` and the verification command passes

#### Scenario: A name that is still there
- **WHEN** a Verification line names `! git grep -n hello src/ tests/` and `src/sample.py` holds `hello`
- **THEN** the step stops with the reason that the command found a match, with the matching lines

#### Scenario: A search that fails
- **WHEN** git exits 128 for the search
- **THEN** the step stops with the reason that holds the status, and the search is no pass

#### Scenario: A path that matches no file
- **WHEN** a Verification line names `! git grep -n hello missing/` and no tracked file is under `missing/`
- **THEN** the step runs `git grep -n hello -- missing/` and the verification command passes

### Requirement: The shell of the agent refuses a command that starts with a bang
The shell of the agent SHALL NOT run a command whose first word is `!`. Only the verification commands of the step run a negative search. The refusal SHALL say to run `git grep -n <literal> -- <paths>`, to read no output as a pass, and that the step runs a verification command that starts with `!` itself. The prompt of the step SHALL say the same.

#### Scenario: The shell of the agent
- **WHEN** the agent runs `! git grep -n x src/` in its shell
- **THEN** the shell refuses the command as a program that is not in the allowed list, the refusal holds the `git grep` form and the sentence that the step runs the `!` command itself, and no process starts

## ADDED Requirements

### Requirement: A negative search has a limit and a reason that is safe to show
The words of a negative search SHALL hold at most 2000 characters in all. A word in the reason of a refusal SHALL be escaped and cut, so that the reason holds no raw line break and no NUL byte, and a stop reason SHALL show the command cut to 2000 characters.

#### Scenario: A search that is too long
- **WHEN** a Verification line names `! git grep -n` followed by a literal of 300000 characters and `src/`
- **THEN** the step stops with the reason that the command is longer than 2000 characters, shows the command cut to 2000 characters, and starts no process

#### Scenario: A word with a control character
- **WHEN** a Verification line names `! git grep -n` followed by a quoted literal that holds a NUL byte or a line break
- **THEN** the reason shows the word with the escapes `\x00` or `\n`, and holds no NUL byte and no line break
