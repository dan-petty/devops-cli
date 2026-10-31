# Spec Delta

## MODIFIED Requirements

### Requirement: Every tool call of a step writes one line to the Job log
The agent of a step SHALL write one line to the standard error stream for each tool call, when it ends. The line SHALL hold the name of the tool, the program of the `command` argument when the tool has one, and the outcome: `ok`, `refused`, `retry` or `failed`. The program SHALL be the first word of the command when it is a program of the allowlist or of `IMPLEMENT_SHELL_REPLACEMENTS`, else `other`. The line SHALL hold nothing else but the reason of a retry.

#### Scenario: A program of the allowlist
- **WHEN** the model calls a tool with the command `git status`
- **THEN** the line holds "program git"

#### Scenario: A call that returns
- **WHEN** the model calls `write_file` with a path and a content, and then ends its run
- **THEN** the standard error stream holds the line "Tool call: write_file, ok." and holds neither the path nor the content

#### Scenario: A call that fails validation
- **WHEN** the model calls `read_file` without its `path` argument
- **THEN** the standard error stream holds the line "Tool call: read_file, retry."

#### Scenario: A short bare word that is no known program
- **WHEN** the first word of a shell command is a short bare word such as `hunter2password` that the model read from a file
- **THEN** the line and the reason of a stopped run hold "other" and not the word

#### Scenario: A refused path
- **WHEN** the model calls `read_file` with a path outside the root
- **THEN** the standard error stream holds the line "Tool call: read_file, retry." and no part of the path

#### Scenario: A call that the tool reports as failed
- **WHEN** a tool reports a failed call
- **THEN** the standard error stream holds the line "Tool call: <tool>, failed."

## ADDED Requirements

### Requirement: A retried tool call writes the reason that the tool returned
After `retry`, the line of a call SHALL hold the message of the `ModelRetry` that the tool raised, in brackets, masked, escaped to one line and cut to `CONST_ROADMAP_IMPLEMENT_LOG_REASON_CHARS` characters. When the message lacks the `path` argument of the call, the line SHALL add "Path: <path>" after it. A retry that is a refusal by policy, and a retry of a failed validation, SHALL have no reason.

#### Scenario: An edit whose old text is missing
- **WHEN** the model calls `edit_file` with an `old_text` that the file does not hold
- **THEN** the line is "Tool call: edit_file, retry (old_text not found in <path>. No changes were written.)." and holds no part of `old_text`

#### Scenario: A retry whose message has no path
- **WHEN** the model calls `edit_file` with a `path` and with neither `old_text` nor `replacements`
- **THEN** the reason in the line ends with "Path: <path>"

#### Scenario: A secret in a reason
- **WHEN** the message of a retry holds a GitHub token
- **THEN** the line holds no part of the token

#### Scenario: A long reason
- **WHEN** the message of a retry is longer than `CONST_ROADMAP_IMPLEMENT_LOG_REASON_CHARS`
- **THEN** the reason in the line is cut to that length and ends with " ..."

#### Scenario: A line break in a reason
- **WHEN** the message of a retry holds a line break or an escape sequence
- **THEN** the line is one line, and it holds the escaped form

#### Scenario: A retry with no reason
- **WHEN** a tool refuses a path outside the root, or the model calls a tool with arguments that fail validation
- **THEN** the line holds no reason

### Requirement: The reason of a retried call shows only a path of the checkout
The line of a retried call SHALL show the `path` argument of the call only when it names a file or a directory of the checkout, and SHALL show "<path>" in its place otherwise. The cut of a long message SHALL leave room for "Path: <path>".

#### Scenario: A long reason without the path
- **WHEN** the message of a retry is longer than `CONST_ROADMAP_IMPLEMENT_LOG_REASON_CHARS` and lacks the `path` argument
- **THEN** the reason in the line is cut and ends with "Path: <path>"

#### Scenario: A path that is no file of the checkout
- **WHEN** the `path` argument is a plain string that no file of the checkout has, and the message names it
- **THEN** the line shows "<path>" in its place and holds no part of the string

### Requirement: The reason of a stopped run names the last retries of the tool that ended it
When a tool exceeds its retries, the reason of the stopped run SHALL end with a line that names the tool and its last `CONST_ROADMAP_IMPLEMENT_STOP_REASONS` reasons, in the form of the Job log. A run that ends on another cause SHALL have no such line.

#### Scenario: A tool that ends the run on retries
- **WHEN** the model calls `edit_file` with an `old_text` that the file does not hold in every reply
- **THEN** the reason ends with a line "Last retries of edit_file: " and the last reasons of that tool, and it holds no part of `old_text`

#### Scenario: A secret in the last reasons
- **WHEN** the message of the last retries holds a GitHub token
- **THEN** the reason holds no part of the token

#### Scenario: Retries with no reason
- **WHEN** the model calls `read_file` without its `path` argument in every reply
- **THEN** the reason holds no line of reasons

#### Scenario: A run that ends on a limit
- **WHEN** the run ends on the request limit after retries of `edit_file`
- **THEN** the reason holds no line of reasons
