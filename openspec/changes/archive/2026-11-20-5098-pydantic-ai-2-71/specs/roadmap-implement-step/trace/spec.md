## MODIFIED Requirements

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
- **WHEN** the model calls `read_file` with a path outside the root in five replies, and its next reply breaks the rules
- **THEN** the reason ends with "Refused commands: 0. Other retries: 5."

#### Scenario: A run with no retry
- **WHEN** the model calls `read_file` with a valid path in every reply until the request limit
- **THEN** the reason holds the message of the error and holds neither count

#### Scenario: The call that spends the retries of a file tool
- **WHEN** the model calls `edit_file` with an `old_text` that the file does not hold in six replies, and its next reply breaks the rules
- **THEN** `Coder` answers the sixth call with a failed result, and the reason ends with "Refused commands: 0. Other retries: 5."

### Requirement: The reason of a stopped run names the last retries of the tool that ended it
When a tool exceeds its retries and ends the run, the reason of the stopped run SHALL end with a line that names the tool and its last `CONST_ROADMAP_IMPLEMENT_STOP_REASONS` reasons, in the form of the Job log. A run that ends on another cause SHALL have no such line. In a step, `Coder` SHALL answer the call that spends the retries of a tool with the last error of the tool as a failed result, and the run SHALL go on.

#### Scenario: A file tool that spends its retries in a step
- **WHEN** the model calls `edit_file` with an `old_text` that the file does not hold in six replies, and its next reply breaks the rules
- **THEN** the sixth call gets a failed result that names the missing file, and the reason holds no line of reasons

#### Scenario: A tool that ends the run on retries
- **WHEN** an agent with the hooks of the log and no `Coder` calls a tool that asks for a retry once more than its retries allow
- **THEN** the reason of the log names the tool and its last three reasons, and shows "<path>" for each path that is no file of the checkout

#### Scenario: A secret in the last reasons
- **WHEN** the message of the last retries holds a GitHub token
- **THEN** the reason holds no part of the token

#### Scenario: Retries with no reason
- **WHEN** the model calls `read_file` without its `path` argument in every reply
- **THEN** the reason holds no line of reasons

#### Scenario: A run that ends on a limit
- **WHEN** the run ends on the request limit after retries of `edit_file`
- **THEN** the reason holds no line of reasons
