# roadmap-implement-step/verification Specification

## Purpose
The verification commands of a task group: their form, the negative search, their limits, and the base replay that shows that the tests of a behavior group fail on the base commit.

## Requirements

### Requirement: The verification commands of a group are the code spans of its Verification lines
The verification commands of a group SHALL be the code spans of the `Verification:` lines of its tasks that start with `$ `, with the mark removed, each one once, in the order of the file. Every other code span of such a line SHALL be prose. The step SHALL run each command as a list of words, never through a shell, and SHALL stop with the reason when the first word is not a program of the verification list or the `!` of a negative search in the fixed shape.

#### Scenario: Two lines name one command
- **WHEN** two tasks of the group name `$ uv run devops ci test tests/test_sample.py` and the second names `$ uv run devops docs check` as well
- **THEN** the step runs `uv run devops ci test tests/test_sample.py` once and `uv run devops docs check` once, in that order

#### Scenario: A prose code span beside a marked command
- **WHEN** a task holds a `Verification:` line with the code span `tagged_image` and the code span `$ pytest tests/roadmap/test_step_files.py`
- **THEN** the commands of the group are `pytest tests/roadmap/test_step_files.py` only

#### Scenario: A line with no mark
- **WHEN** a task holds a `Verification:` line with the code span `pytest tests/roadmap/test_step_files.py` and no mark
- **THEN** the group has no command from that line

#### Scenario: A marked command that the step refuses
- **WHEN** a task holds the code span `$ nosuchprogram --version` on its `Verification:` line
- **THEN** the step stops with a reason that names `nosuchprogram` as a program that is not in the allowed list

### Requirement: A negative search is a verification command in a fixed shape
The step SHALL run a verification command that starts with `!` only as `! git grep [options] <literal> [--] <path>...` or as `! git grep [options] -e <literal> [-e <literal>]... -- <path>...`, with at least one path and with the options `-n -I -F -i -w -l -c -q` in words of those letters. The step SHALL start no process for a command outside the shape, and the reason of the stop SHALL say which rule of the shape the command breaks.

#### Scenario: A command that is not the fixed shape
- **WHEN** a Verification line names `! rm -rf src/`, `! git grep -n name src/ | cat`, `! git grep -n name src/ ; ls`, `! git grep -n name src/ && ls`, `! git grep -n name src/ > out.txt`, `! git grep -n '$(id)' src/`, `! git grep -O name src/`, `! git grep --no-index -n name src/`, `! git grep -f patterns.txt src/`, `! git grep --open-files-in-pager=cat name src/`, `! git grep -n name /etc` or `! git grep -n name ../other`
- **THEN** the step stops with the reason that says which rule of the shape the command breaks, and starts no process

#### Scenario: A letter outside ASCII
- **WHEN** a Verification line names a literal with a fullwidth `ｆ` or an accented `é`, or a path with one
- **THEN** the step stops with the reason that the text is not a literal, or that the word is not a path, and starts no process

### Requirement: The literal and the paths of a negative search are plain
The literal SHALL hold only letters, digits, spaces and the signs `_ . : / = @ + , # % ~ -`. A path SHALL be relative, SHALL hold only letters, digits and the signs `_ . + @ ~ * / -`, SHALL NOT start with `-`, and SHALL NOT have a `..` part.

#### Scenario: A literal or a path that is not plain
- **WHEN** a Verification line names `! git grep -n 'a|b' src/` or `! git grep -n name :(top)src`
- **THEN** the step stops with the reason that names the text or the word, and starts no process

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

### Requirement: A behavior group's tests fail on the base commit

The implement step SHALL replay the test files of a behavior group on the base commit of the group, with the tests of the head overlaid. The step SHALL accept the group only when one test of those files fails in its call phase on the base commit.

#### Scenario: Tests pass on base

- **WHEN** every test of the test files of a behavior group passes on the base commit
- **THEN** the step stops with a message that names the test files, and it gets a repair round of `roadmap.implement.repair_rounds` that may change only test files.

#### Scenario: Tests error on base

- **WHEN** a test file of a behavior group stops with an error on the base commit, before any assertion runs, and no test of the group fails there
- **THEN** the step stops with a message, and the error does not count as a failure on the base commit.

#### Scenario: A test fails on base

- **WHEN** a test of a behavior group fails in its call phase on the base commit and passes after the change
- **THEN** the step continues with the other exit checks.

#### Scenario: No test file changed

- **WHEN** a behavior group changes no test file
- **THEN** the step stops with a message and gets no repair round.

### Requirement: The trace holds each base replay

The implement step SHALL add one check event to the trace for each replay of a behavior group on the base commit. The event SHALL hold the exit status of the replay.

#### Scenario: A replay is a check event

- **WHEN** the step replays the tests of a behavior group on the base commit
- **THEN** the trace holds one check event for the replay, with its exit status.

### Requirement: The PR comment shows the fail-to-pass result of each behavior group

The PR comment of a step SHALL show one line for each behavior group that the step replayed on the base commit. The line SHALL name the group, the result on the base commit and the tests that failed there.

#### Scenario: A behavior group is replayed

- **WHEN** the step replays a behavior group on the base commit, and the group then passes or stops
- **THEN** the PR comment holds one line that names the group, the result of the replay and the failed test.

### Requirement: A group of kind other records its verify output

The implement step SHALL keep the output of each verification command of a group of kind `other` that passes. The PR comment SHALL show each command with its exit status and its masked, bounded output.

#### Scenario: A verify command of an other group prints a line

- **WHEN** a group of kind `other` passes its verify command, and the command prints one line
- **THEN** the step outcome holds that command, its exit status and that line.

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
