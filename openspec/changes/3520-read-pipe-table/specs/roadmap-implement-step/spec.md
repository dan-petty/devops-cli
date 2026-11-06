## MODIFIED Requirements

### Requirement: The shell tool admits only the project's programs
The shell tool SHALL run a command only when its first word is a program of `SHELL_PROGRAMS` and it holds no operator that starts a second command (a pipe to a program of `CONST_ROADMAP_IMPLEMENT_READ_PIPE_PROGRAMS` and the prefix `cd <checkout> &&` are not such an operator), no redirect to a file in a read-only program, and no refused argument or `$` word in `find`. Any other command SHALL come back as a normal tool result that holds the refusal and a hint, and the run SHALL go on. A refusal SHALL add no tool retry. The shell SHALL run with `HOME` set to a temporary directory. The shell is no security boundary.

#### Scenario: A program outside the list
- **WHEN** the model calls the shell tool with `curl http://example.com`, and then ends its run
- **THEN** the call returns the refusal that `curl` is not in the allowed list followed by the list of the allowed programs, no process starts, and the run ends with the last message of the model

#### Scenario: The devops command
- **WHEN** the model calls the shell tool with `devops gh api -X POST repos/example/roadmap/issues`
- **THEN** the call returns the refusal that `devops` is not in the allowed list, and no process starts

#### Scenario: A second command
- **WHEN** the model calls the shell tool with `git status; curl http://example.com`
- **THEN** the call returns a refusal that names the operator and states the rule of one command in each call, and no process starts

#### Scenario: A habit of the table
- **WHEN** the model calls the shell tool with `python -m pytest`
- **THEN** the refusal holds "Instead of `python`: `uv run python`" and says that `python -m pip` is not to run, and no process starts

#### Scenario: A long word
- **WHEN** the model calls the shell tool with a first word of 5000 characters
- **THEN** the refusal holds the text of the shell cut to `CONST_ROADMAP_RUN_ERROR_CHARS` characters, then the hint

#### Scenario: A read-only program
- **WHEN** the model calls the shell tool with `grep -rn shout src`, `cat README.md`, `ls src`, `head -n 5 README.md` or `find src -name "*.py"`
- **THEN** the command runs and the call returns its output

#### Scenario: A file command
- **WHEN** the model calls the shell tool with `rg shout src`
- **THEN** the refusal names the tool `grep`

#### Scenario: A find that runs or deletes
- **WHEN** the model calls the shell tool with `find . -name "*.py" -exec rm {} +`
- **THEN** the refusal names `find` and `-exec`, says to use `find` to list paths only, and no process starts

#### Scenario: A redirect to a file
- **WHEN** the model calls the shell tool with `grep -rn x src > out.txt`, `cat a >> b` or `ls > f`
- **THEN** the refusal names the program and the redirect, says to use `write_file` or `edit_file`, counts as a refused command, and no process starts. `2>&1` and `>/dev/null` still run.

#### Scenario: A find with an expansion
- **WHEN** the model calls the shell tool with `find . -ex${U}ec echo {} +`, because the shell expands `${U}` after the check
- **THEN** the refusal names `find` and the word, and no process starts

#### Scenario: A change of directory
- **WHEN** the model calls the shell tool with `cd src`
- **THEN** the refusal says that `cd` is not needed because every command runs in the checkout

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

#### Scenario: The retry limit is unchanged
- **WHEN** the model calls the shell tool with `python -V` in more replies than `CONST_ROADMAP_IMPLEMENT_TOOL_RETRIES`, and then ends its run
- **THEN** each call returns the refusal with its hint as a tool result and not as a retry, the run is not stopped for retries, and the limit of `CONST_ROADMAP_IMPLEMENT_TOOL_RETRIES` still holds for the failures of a tool

#### Scenario: A real failure of a tool still counts
- **WHEN** the model calls `read_file` without its `path` argument in more replies than `CONST_ROADMAP_IMPLEMENT_TOOL_RETRIES`
- **THEN** the run ends stopped with the tool retry limit as before

#### Scenario: The prompt and the table agree
- **WHEN** the prompt of the step is built, the shell is configured, or `docs/ROADMAP_WORKFLOW.md` is read
- **THEN** the programs and the refusals in the prompt and the document are the text that `SHELL_PROGRAMS` and `SHELL_REFUSALS` give, the allowlist of the shell is the names of `SHELL_PROGRAMS`, and a shell command of the prompt holds no operator that the shell refuses

### Requirement: Every tool call of a step writes one line to the Job log
The agent SHALL write one line to the standard error stream when each tool call ends. The line SHALL hold the name of the tool, the program of the `command` argument when the tool has one, and the outcome: `ok`, `refused`, `retry` or `failed`. A shell refusal has the outcome `refused`. The program SHALL be the first word of the command when it is a program of the allowlist or of `IMPLEMENT_SHELL_REPLACEMENTS`, else `other:` and the first 12 hexadecimal characters of the HMAC-SHA256 of the word, with a random key of the process. A command that starts with `cd <checkout> &&` SHALL name the program after the prefix. The line SHALL hold nothing else but the reason of a retry.

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
- **THEN** the line and the reason of a stopped run hold "other:" and the 12-character digest of the word, and not the word

#### Scenario: A known program of the pipe table
- **WHEN** the model calls the shell tool with `wc -l README.md`
- **THEN** the line holds "program wc"

#### Scenario: An unknown first word
- **WHEN** the first word of a shell command is `secret-tool`, which is no known program
- **THEN** the line holds "program other:" and a 12-character hexadecimal digest, and holds neither `secret-tool` nor the rest of the command

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
The log line of a shell call whose first word is `!` SHALL name the program `other` with its digest and SHALL show no word after it.

#### Scenario: A bang command
- **WHEN** the agent calls the shell with `! Authorization: Bearer abcdef0123456789abcdef`
- **THEN** the log line says `program other:` and the digest, and holds no word of the command
