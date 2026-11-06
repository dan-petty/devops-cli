## ADDED Requirements

### Requirement: The shell admits a read pipe and the checkout prefix
The shell tool SHALL run a command with a pipe when each stage after the first is a program of `CONST_ROADMAP_IMPLEMENT_READ_PIPE_PROGRAMS` that writes no file. It SHALL read a `|` in quotes or after a backslash as part of a word. It SHALL run a command that starts with the exact prefix `cd <checkout> &&` without that prefix. `|` SHALL stay in `CONST_ROADMAP_IMPLEMENT_DENIED_OPERATORS`.

#### Scenario: A read pipe
- **WHEN** the model calls the shell tool with `git status | head -n 5`, `git show HEAD:README.md | head -100`, `head -n 170 README.md | tail -n 20` or `git status | head | wc -l`
- **THEN** the command runs and the call returns its output

#### Scenario: A pattern with an alternation
- **WHEN** the model calls the shell tool with `grep -n 'shutil\|subprocess' README.md` or `grep -n "a|b" README.md`
- **THEN** the command runs, because the pipe character is part of a word

#### Scenario: A pipe to another program
- **WHEN** the model calls the shell tool with `git status | sh`, `ls | head | sh` or `ls |& head`
- **THEN** the call returns a refusal that names the program or the operator and lists `CONST_ROADMAP_IMPLEMENT_READ_PIPE_PROGRAMS`, and no process starts

#### Scenario: A pipe that writes a file
- **WHEN** the model calls the shell tool with `git status | head > out.txt`
- **THEN** the call returns the refusal of the redirect for `head`, and no process starts

#### Scenario: Another operator after a read pipe
- **WHEN** the model calls the shell tool with `git status | head; ls`
- **THEN** the call returns a refusal that names the operator `;`, and no process starts

#### Scenario: The checkout prefix
- **WHEN** the model calls the shell tool with `cd <checkout> && git status | head` and `<checkout>` is the checkout of the step
- **THEN** the command runs without the prefix

#### Scenario: Another chain with a change of directory
- **WHEN** the model calls the shell tool with `cd <checkout> && git status && ls`, or with `cd src && ls`
- **THEN** the call returns a refusal, and no process starts

#### Scenario: The pipe stays a denied operator
- **WHEN** a test reads `CONST_ROADMAP_IMPLEMENT_DENIED_OPERATORS` and `CONST_ROADMAP_IMPLEMENT_READ_PIPE_PROGRAMS`
- **THEN** the first holds `|`, and the second holds `head`, `tail`, `grep` and `wc` and only programs of `SHELL_PROGRAMS` with access `read`

## MODIFIED Requirements

### Requirement: Every tool call of a step writes one line to the Job log
The agent SHALL write one line to the standard error stream when each tool call ends. The line SHALL hold the name of the tool, the program of the `command` argument when the tool has one, and the outcome: `ok`, `refused`, `retry` or `failed`. A shell refusal has the outcome `refused`. The program SHALL be the first word of the command when it is a program of the allowlist or of `IMPLEMENT_SHELL_REPLACEMENTS`, else `other:<digest>`. The line SHALL hold nothing else but the reason of a retry.

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
- **THEN** the line and the reason of a stopped run hold "other:" and a digest, and not the word

#### Scenario: A known program of the pipe table
- **WHEN** the model calls the shell tool with `wc -l README.md`
- **THEN** the line holds "program wc"

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

### Requirement: The log names no word after a bang
The log line of a shell call whose first word is `!` SHALL name the program `other:<digest>` and SHALL show no word after it.

#### Scenario: A bang command
- **WHEN** the agent calls the shell with `! Authorization: Bearer abcdef0123456789abcdef`
- **THEN** the log line says `program other:` and a digest, and holds no word of the command
