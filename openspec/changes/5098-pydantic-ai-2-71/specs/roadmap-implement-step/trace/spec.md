## MODIFIED Requirements

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
