## ADDED Requirements

### Requirement: The reason of a stopped run counts the retried tool calls
A step that stops on a pydantic-ai error SHALL count the tool calls that came back as a retry for a cause other than a policy of the project, and the reason SHALL end with that count when it is not zero.

#### Scenario: Retried calls
- **WHEN** the model calls a file tool without its path argument in six replies, and its next reply breaks the rules
- **THEN** the reason ends with a new line and Other retries: 6.

## MODIFIED Requirements

### Requirement: Every tool call of a step writes one line to the Job log
The agent SHALL write one line to the standard error stream when each tool call ends. The line SHALL hold the name of the tool, the program of its `command` argument when it has one, and the outcome: `ok`, `refused`, `retry` or `failed`. The program SHALL be the first word of the command when `RUNNER_TOOLS` holds it, else `other:<digest>`. The line SHALL hold nothing else but the reason of a retry.

#### Scenario: A program of the allowlist
- **WHEN** the model calls a tool with the command `git status`
- **THEN** the line holds "program git", because `git` is a program of `RUNNER_TOOLS`

#### Scenario: A call that returns
- **WHEN** the model calls `write_file` with a path and a content, and then ends its run
- **THEN** the standard error stream holds the line "Tool call: write_file, ok." and holds neither the path nor the content

#### Scenario: A call that fails validation
- **WHEN** the model calls `read_file` without its `path` argument
- **THEN** the standard error stream holds the line "Tool call: read_file, retry."

#### Scenario: A short bare word that is no known program
- **WHEN** the first word of a shell command is a short bare word such as `hunter2password` that the model read from a file
- **THEN** the line and the reason of a stopped run hold "other:" and a digest, and not the word

#### Scenario: A known program of the pipe table
- **WHEN** the model calls the shell tool with `wc -l README.md`
- **THEN** the line holds "program other:" and 12 hexadecimal characters, because `wc` is no program of `RUNNER_TOOLS`

#### Scenario: An unknown first word
- **WHEN** the first word of a shell command is `secret-tool`, which is no known program
- **THEN** the line holds "program other:" and 12 hexadecimal characters, and holds neither `secret-tool` nor the rest of the command

#### Scenario: A digest with a key
- **WHEN** the first word is `hunter2password`, and it is no known program
- **THEN** the digest is the first 12 hexadecimal characters of an HMAC-SHA256 of the word with a random key of the process, so it is not the plain SHA-256 of the word, and the same word has the same digest in one run

#### Scenario: The checkout prefix
- **WHEN** the model calls the shell tool with `cd <checkout> && python -V`
- **THEN** the lines hold "started: python -V" and "program python", and not "program cd"

#### Scenario: A refused path
- **WHEN** the model calls `read_file` with a path outside the root
- **THEN** the standard error stream holds the line "Tool call: read_file, retry." and no part of the path

#### Scenario: A call that the tool reports as failed
- **WHEN** a tool reports a failed call
- **THEN** the standard error stream holds the line "Tool call: <tool>, failed."

## REMOVED Requirements

### Requirement: The reason of a stopped run counts the refused and the retried tool calls
**Reason**: The step refuses no command by a policy of the project, so the reason counts no refused command by program.
**Migration**: The reason of a stopped run counts the retried tool calls
