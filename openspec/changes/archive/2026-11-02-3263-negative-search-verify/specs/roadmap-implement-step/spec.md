# Spec Delta

## MODIFIED Requirements

### Requirement: The verification commands of a group are the code spans of its Verification lines
The verification commands of a group SHALL be the code spans of the `Verification:` lines of its tasks, each one once, in the order of the file. The step SHALL run each one in the checkout as a list of words, never through a shell. It SHALL refuse to run one whose first word is not a program of the verification list (the shell allowlist, `openspec` and `devops`) and is not the `!` of a negative search in the fixed shape.

#### Scenario: Two lines name one command
- **WHEN** two tasks of the group name `uv run devops ci test tests/test_sample.py` and the second names `uv run devops docs check` as well
- **THEN** the step runs `uv run devops ci test tests/test_sample.py` once and `uv run devops docs check` once, in that order

## ADDED Requirements

### Requirement: A negative search is a verification command in a fixed shape
The step SHALL run a verification command that starts with `!` only as `! git grep [options] <literal> [--] <path>...`, with at least one path and with the options `-n -I -F -i -w -l -c -q` in words of those letters. The step SHALL start no process for a command outside the shape, and the reason of the stop SHALL say which rule of the shape the command breaks.

#### Scenario: A command that is not the fixed shape
- **WHEN** a Verification line names `! rm -rf src/`, `! git grep -n name src/ | cat`, `! git grep -n name src/ ; ls`, `! git grep -n name src/ && ls`, `! git grep -n name src/ > out.txt`, `! git grep -n '$(id)' src/`, `! git grep -O name src/`, `! git grep --no-index -n name src/`, `! git grep -f patterns.txt src/`, `! git grep --open-files-in-pager=cat name src/`, `! git grep -n name /etc` or `! git grep -n name ../other`
- **THEN** the step stops with the reason that says which rule of the shape the command breaks, and starts no process

### Requirement: The literal and the paths of a negative search are plain
The literal SHALL hold only letters, digits, spaces and the signs `_ . : / = @ + , # % ~ -`. A path SHALL be relative, SHALL hold only letters, digits and the signs `_ . + @ ~ * / -`, SHALL NOT start with `-`, and SHALL NOT have a `..` part.

#### Scenario: A literal or a path that is not plain
- **WHEN** a Verification line names `! git grep -n 'a|b' src/` or `! git grep -n name :(top)src`
- **THEN** the step stops with the reason that names the text or the word, and starts no process

### Requirement: A negative search passes when git finds no match
The step SHALL run a negative search as `git grep` with the options, the literal, `--` and the paths, with no shell. The search SHALL pass when git exits 1. It SHALL stop the step with the matching lines when git exits 0, and with the status when git exits with any other status.

#### Scenario: A name that is gone
- **WHEN** a Verification line names `! git grep -n absent_name src/ tests/` and no file holds `absent_name`
- **THEN** the step runs `git grep -n absent_name -- src/ tests/` and the verification command passes

#### Scenario: A name that is still there
- **WHEN** a Verification line names `! git grep -n hello src/ tests/` and `src/sample.py` holds `hello`
- **THEN** the step stops with the reason that the command found a match, with the matching lines

#### Scenario: A search that fails
- **WHEN** git exits 128 for the search
- **THEN** the step stops with the reason that holds the status, and the search is no pass

### Requirement: The shell of the agent refuses a command that starts with a bang
The shell of the agent SHALL NOT run a command whose first word is `!`. Only the verification commands of the step run a negative search.

#### Scenario: The shell of the agent
- **WHEN** the agent runs `! git grep -n x src/` in its shell
- **THEN** the shell refuses the command as a program that is not in the allowed list, and starts no process
