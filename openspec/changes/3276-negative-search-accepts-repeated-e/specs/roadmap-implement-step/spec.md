## MODIFIED Requirements

### Requirement: A negative search is a verification command in a fixed shape
The step SHALL run a verification command that starts with `!` only as `! git grep [options] <literal> [--] <path>...` or as `! git grep [options] -e <literal> [-e <literal>]... -- <path>...`, with at least one path and with the options `-n -I -F -i -w -l -c -q` in words of those letters. The step SHALL start no process for a command outside the shape, and the reason of the stop SHALL say which rule of the shape the command breaks.

#### Scenario: A command that is not the fixed shape
- **WHEN** a Verification line names `! rm -rf src/`, `! git grep -n name src/ | cat`, `! git grep -n name src/ ; ls`, `! git grep -n name src/ && ls`, `! git grep -n name src/ > out.txt`, `! git grep -n '$(id)' src/`, `! git grep -O name src/`, `! git grep --no-index -n name src/`, `! git grep -f patterns.txt src/`, `! git grep --open-files-in-pager=cat name src/`, `! git grep -n name /etc` or `! git grep -n name ../other`
- **THEN** the step stops with the reason that says which rule of the shape the command breaks, and starts no process

#### Scenario: A letter outside ASCII
- **WHEN** a Verification line names a literal with a fullwidth `ｆ` or an accented `é`, or a path with one
- **THEN** the step stops with the reason that the text is not a literal, or that the word is not a path, and starts no process

## ADDED Requirements

### Requirement: A negative search takes repeated -e literals
The step SHALL read each `-e` option of a negative search as the option that takes the literal after it. Each such literal SHALL hold only the characters of a positional literal and SHALL NOT start with `-`. The step SHALL run `git grep` with each literal after its own `-e`, and SHALL pass the search when git exits 1.

#### Scenario: Two names that do not occur
- **WHEN** a Verification line names `! git grep -n -e "ImagetoolsFake" -e "inspect_command" -- src tests` and no file under `src` or `tests` holds either name
- **THEN** the step runs `git grep -n -e ImagetoolsFake -e inspect_command -- src tests` and the verification command passes

#### Scenario: One of the names occurs
- **WHEN** a Verification line names `! git grep -n -e hello -e absent_name -- src/ tests/` and `src/sample.py` holds `hello`
- **THEN** the step stops with the matching lines that git printed, and starts no other process

#### Scenario: A value that is not a plain literal
- **WHEN** a Verification line names `! git grep -n -e 'a|b' -- src/`, `! git grep -n -e 'a;b' -- src/` or `! git grep -n -e -- src/`
- **THEN** the step stops with the reason that names the text, or that the `-e` option has no literal, and starts no process

#### Scenario: A value that starts with -
- **WHEN** a Verification line names `! git grep -n -e -E -- src/` or `! git grep -n -e --addons -- src/`
- **THEN** the step stops with the reason that the text starts with `-`, and starts no process

### Requirement: A negative search with -e puts -- before its paths
A negative search with `-e` options SHALL have `--` after its last literal and before its paths. It SHALL NOT have a word between the last literal and `--`.

#### Scenario: Both forms in one line
- **WHEN** a Verification line names `! git grep -e name literal -- src/`, or `! git grep -e name src/`
- **THEN** the step stops with the reason that names both forms of the search, and starts no process
