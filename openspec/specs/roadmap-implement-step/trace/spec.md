# roadmap-implement-step/trace Specification

## Purpose
The log and the trace of an implement step: the line of each tool call, the events in the order of the run, the masked texts, and the reason of a stopped run.

## Requirements

### Requirement: The outcome is a structured report
The step SHALL return a `StepOutcome` with the status (done or stopped), the reason, the last message of the agent, the commit, the repair rounds used, and the requests, the tool calls and the tokens that the run spent. The command SHALL print it as a table, or as JSON with `--format json`, and SHALL exit 1 when the status is stopped. The step SHALL record the spend of the run as one record of the spend ledger.

#### Scenario: A stopped step as JSON
- **WHEN** a step stops on a failed verification and the command runs with `--format json`
- **THEN** the output is one JSON object with `status` `stopped`, the reason, an empty `commit`, and the counts of requests, tool calls and tokens, and the exit code is 1

#### Scenario: The spend record
- **WHEN** a step ends after two model requests
- **THEN** the spend ledger holds one record for the run with the sum of the tokens of the two replies

#### Scenario: The tool calls
- **WHEN** a step ends after three tool calls in two replies
- **THEN** the outcome holds `tool_calls` 3

#### Scenario: The repair rounds
- **WHEN** a step ends after one extra turn
- **THEN** the outcome holds `repair_rounds` 1 and the table shows the count

### Requirement: A stopped step reports a masked diff of its discarded work
A step that ends as stopped SHALL read the diff of the work that it discards, from its start commit to the checkout, new files included, with no external diff program or text conversion. It SHALL mask secrets in the diff with `mask_secrets` first, then cut it to `CONST_ROADMAP_IMPLEMENT_DIFF_CHARS` characters. The `StepOutcome` SHALL hold the result as `diff`, and SHALL set `diff_cut` when it cut the diff or the part that it masked. A done step SHALL report an empty diff.

#### Scenario: A stop after the agent wrote files
- **WHEN** the agent writes `src/sample.py` and a new test file, and the step stops on a failed verification command
- **THEN** the outcome holds a diff that names both files and holds their new lines, and the checkout is reset

#### Scenario: A long diff
- **WHEN** the discarded work is longer than `CONST_ROADMAP_IMPLEMENT_DIFF_CHARS` characters
- **THEN** the diff of the outcome is exactly that long and `diff_cut` is true

#### Scenario: A secret in the diff
- **WHEN** the agent writes a line that holds a token in the form of a GitHub token and the step stops
- **THEN** the diff of the outcome holds the mask in place of the token

#### Scenario: A done step
- **WHEN** the step ends done
- **THEN** its diff is empty and `diff_cut` is false

### Requirement: A stopped step reads a bounded diff that may hold bytes that are not UTF-8
A stopped step SHALL give `mask_secrets` at most `CONST_ROADMAP_IMPLEMENT_DIFF_READ_CHARS` characters of the diff, a multiple of `CONST_ROADMAP_IMPLEMENT_DIFF_CHARS`, and SHALL set `diff_cut` when git printed more. It SHALL read the output of git with a replacement character for each byte that is not UTF-8, and SHALL raise no decode error.

#### Scenario: A very large diff
- **WHEN** the discarded work is longer than `CONST_ROADMAP_IMPLEMENT_DIFF_READ_CHARS` characters
- **THEN** `mask_secrets` gets at most that many characters, the diff of the outcome is cut to `CONST_ROADMAP_IMPLEMENT_DIFF_CHARS` characters and `diff_cut` is true

#### Scenario: A file that is not UTF-8
- **WHEN** the discarded work holds a Latin-1 file
- **THEN** the step reports stopped with a diff that holds a replacement character in place of each byte that is not UTF-8, and raises no error

### Requirement: The reason of a stopped run counts the refused and the retried tool calls
A step that stops on a pydantic-ai error SHALL count the tool calls that a tool refused by its policy, by program, and the tool calls that came back as a retry for another cause. The reason SHALL end with both counts when a count is not zero. It SHALL list at most `CONST_ROADMAP_IMPLEMENT_REFUSED_PROGRAMS` programs, most refused first, and join the rest to `other`. A call counts as refused when the shell refused its command or an argument by its policy.

#### Scenario: The call that exceeds the limit
- **WHEN** the model is refused more often than `roadmap.implement.max_refusals` times, or `roadmap.implement.max_consecutive_refusals` times in a row
- **THEN** the call that ends the run counts as refused too

#### Scenario: Refused commands
- **WHEN** the model calls the shell tool with `pytest tests/test_sample.py` in every reply, and `pytest` is not a program of the shell table
- **THEN** the reason ends with a new line and "Refused commands: pytest 3. Other retries: 0.", where 3 is `roadmap.implement.max_consecutive_refusals`

#### Scenario: Refused commands of two programs
- **WHEN** the model is refused `python` four times and `cd` twice, and then another error ends the run
- **THEN** the reason ends with "Refused commands: python 4, cd 2."

#### Scenario: Refused commands of many programs
- **WHEN** the model is refused more distinct programs than `CONST_ROADMAP_IMPLEMENT_REFUSED_PROGRAMS`
- **THEN** the reason lists that number of programs and the count of `other` holds the rest

#### Scenario: Arguments that fail validation
- **WHEN** the model calls the tool `read_file` without its `path` argument in every reply
- **THEN** the reason ends with "Refused commands: 0. Other retries: 6."

#### Scenario: A path outside the root
- **WHEN** the model calls `read_file` with the path `/etc/passwd` in every reply
- **THEN** the reason ends with "Refused commands: 0. Other retries: 6."

#### Scenario: A run with no retry
- **WHEN** the model calls `read_file` with a valid path in every reply until the request limit
- **THEN** the reason holds the message of the error and holds neither count

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

### Requirement: A call with a command writes the command to the Job log before it runs
Before a call that has a `command` runs, the agent SHALL write the line `Tool call: <tool>, started: <command>`. The command SHALL be the first word and at most `CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_WORDS` words, escaped and cut to `CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_CHARS` characters. The line SHALL hide each secret, the value of each `name=value` word that is not a number, and each word with a space. When the first word is no known program, the command SHALL be `other`.

#### Scenario: A refused program
- **WHEN** the model calls `run_command` with `pytest tests/test_sample.py`, and then ends its run
- **THEN** the standard error stream holds the lines "Tool call: run_command, started: pytest tests/test_sample.py" and "Tool call: run_command, program pytest, refused."

#### Scenario: The line comes before the call
- **WHEN** the model calls `run_command` with `uv run pytest -n 48`, and the tool is still running
- **THEN** the standard error stream holds the line "Tool call: run_command, started: uv run pytest -n 48" and no line with an outcome

#### Scenario: A long command
- **WHEN** the command has more words than `CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_WORDS`, or more characters than `CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_CHARS`
- **THEN** the line holds the first words, cut, and ends with " ..."

#### Scenario: A secret in an argument
- **WHEN** the command is `git remote add origin https://user:ghp_<token>@example.com/x.git`, with a GitHub token in place of `<token>`
- **THEN** the line holds no part of the token

#### Scenario: A value after a name
- **WHEN** an argument has the form `name=value` and the value is not a number, for example `ai.api_key=<value>` or `http.extraheader=AUTHORIZATION: basic <value>`
- **THEN** the line holds the name and the word `<masked>` in place of the value, and an argument with a number as the value, such as `--numprocesses=48`, stays as it is

#### Scenario: Free text in an argument
- **WHEN** an argument holds a space, as the message of a commit does
- **THEN** the line holds the word `<masked>` in place of the argument

#### Scenario: A control character in an argument
- **WHEN** an argument holds an escape sequence or another control character that is no space
- **THEN** the line is one line, and it holds the escaped form of the character

#### Scenario: A first word that is no program
- **WHEN** the first word of a shell command is an assignment such as `API_KEY=hunter2`, a path, a word with a space or a quote, an escape sequence, or the command has an unclosed quote
- **THEN** the lines hold "started: other" and "program other" and hold no part of the command

### Requirement: The table of a stopped step shows the reason as text
The table of `devops roadmap implement` SHALL print the reason and the last message as text. A bracket in either SHALL NOT be read as markup, and SHALL NOT raise an error.

#### Scenario: A reason with a closing tag
- **WHEN** the reason of a stopped step is "Tool x [/oops] failed"
- **THEN** the table holds that text

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

### Requirement: A step records its model calls and its tool calls
When the job gives a step a trace, the step SHALL add one event for each model call, with the model name, the input and output tokens and the seconds, and one event for each tool call, with the tool, the program, the digest of its masked argument and the outcome `ok`, `refused`, `retry` or `failed`. A retry SHALL hold the reason that the Job log shows.

#### Scenario: Two model calls
- **WHEN** a step ends after two model replies of 100 and 120 input tokens
- **THEN** the trace holds two `model` events with those input tokens, the model name and a number of seconds from the time of each request and its reply

#### Scenario: A refused command and a retried edit
- **WHEN** the model runs a command that the shell policy refuses, and an `edit_file` whose `old_text` is missing
- **THEN** the trace holds a `tool` event with the outcome `refused` and the program, and a `tool` event with the outcome `retry` and the reason of the tool

#### Scenario: The digest of an argument
- **WHEN** the model makes the same call twice and a third call with another command
- **THEN** the first two events hold the same digest of 12 hexadecimal characters, the third holds another, and no event holds the command

### Requirement: A step records its checks and its retries
The step SHALL add one event for each command that it runs as an exit check, with the command and its exit status, and one event for each repair round and each send again of a model request, with the reason.

#### Scenario: A failed lint and one repair round
- **WHEN** `ruff check` exits 1 on the files of a step, a repair round fixes them, and the check exits 0
- **THEN** the trace holds a `check` event with exit status 1, a `retry` event with the reason, and a `check` event with exit status 0, in that order

#### Scenario: A command that runs out of time
- **WHEN** a check command exceeds the command timeout
- **THEN** the `check` event holds no exit status and says that it timed out

### Requirement: Every text of an event is masked
The step SHALL pass each text of an event through `bounded_text` and `mask_private_hosts` and escape it to one line, and SHALL build the digest from the argument with each secret-named value hidden. An event SHALL hold no secret and no private host name.

#### Scenario: A secret and a host in a reason
- **WHEN** the reason of a retry holds `Bearer abcdefghijklmnopqrstuvwxyz0123` and `db.corp.internal`
- **THEN** the event holds `<masked-token>` and `<masked-host>`, and neither original text

#### Scenario: A secret-named argument
- **WHEN** two calls differ only in the value of the argument `api_key`
- **THEN** their events hold the same digest and neither value

### Requirement: A step records each attempt
The step SHALL add one `attempt` event to the trace for the first run and for each repair round. The event SHALL hold the number of the attempt, the tier, the outcome `passed` or `failed`, the failure class of a failed attempt, its evidence, and `repair` or `stop` for what follows. The evidence SHALL pass the masking of every text of an event.

#### Scenario: A failing check that passes on the second attempt
- **WHEN** `ruff check` exits 1 after the first run, and the model fixes the file in the repair round
- **THEN** the trace holds two `attempt` events: attempt 1 failed with class `lint` and the evidence of `ruff`, followed by `repair`, and attempt 2 passed

#### Scenario: A stop
- **WHEN** the repair rounds are used and the check still fails
- **THEN** the last `attempt` event is failed and followed by `stop`

#### Scenario: A fatal class
- **WHEN** the group changes no file
- **THEN** the trace holds one `attempt` event, failed with class `plan_defect` and followed by `stop`

### Requirement: A step records the form check in its trace
The implement step SHALL record one check event for each test-form check, and the event SHALL name the test file, the named count, the collected count and the result.

#### Scenario: The trace holds the form check
- **WHEN** the step checks a test that a task names
- **THEN** the trace holds a check event with the test file and the named and collected counts.

#### Scenario: A task names no count
- **WHEN** the task names a parametrized test with no case count
- **THEN** the check event names the test file and the collected count and records the result.

### Requirement: The events of a trace stand in the order of the run
The step SHALL add the model event of a reply when the reply comes, so that the events stand in the order of the run: a reply, then the tool calls that it asks for. A reply that the step never receives whole, such as one that the output cap cut, SHALL get its event when its turn ends.

#### Scenario: The order of the events
- **WHEN** a step ends after a reply with one tool call, a reply with two tool calls and a last reply
- **THEN** the kinds of the events are `model`, `tool`, `model`, `tool`, `tool`, `model`, then the `attempt` event

#### Scenario: A long run
- **WHEN** a step makes 101 requests and 150 tool calls, and the events do not fit `CONST_ROADMAP_IMPLEMENT_TRACE_CHARS` characters
- **THEN** the encoded trace is not longer than the bound, it holds no `model` event, it holds the newest `tool` events in the order of the run and then the `attempt` event, and `dropped` counts the 101 model events and the older tool events

### Requirement: A shell call in a trace holds its exit status
The `tool` event of a `run_command` call SHALL hold `status`, the exit code of the command, and no text of its output: the code of the last line `[exit code: <n>]`, else 0. A call whose command ran past its wait, a refused call and a call of another tool SHALL hold no `status`.

#### Scenario: The exit status of a shell call
- **WHEN** the result of a `run_command` call ends with the line `[exit code: 128]`
- **THEN** the `tool` event holds `status` 128 and no text of the output

#### Scenario: A command that exits with 0
- **WHEN** the result of a `run_command` call has no line of an exit code
- **THEN** the `tool` event holds `status` 0

#### Scenario: A shell call with no status
- **WHEN** the result of a `run_command` call ends with the line of the timeout
- **THEN** the `tool` event holds no `status`
