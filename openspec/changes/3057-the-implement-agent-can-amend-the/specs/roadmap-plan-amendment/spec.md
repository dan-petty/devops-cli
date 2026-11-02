## Purpose
What the implement job takes from an agent as a request to change its plan, which changes the job applies by itself to the `tasks.md` of the change, how it records them, and which requests wait for a person.

## ADDED Requirements

### Requirement: A request is the last fenced block of the last message
A request SHALL be one JSON object in a fenced block with the info string `plan-request` that ends the last message of a stopped step. Its keys are `kind` (`path`, `command`, `task`, `premise` or `scope`), `group`, `defect`, `evidence` and, by kind, `old`, `new` and `verify`. A message with no such block, a block that text follows, or an object with an unknown key or kind SHALL hold no request.

#### Scenario: A block ends the message
- **WHEN** the last message of a step ends with a `plan-request` block that holds the kind `path`, the group 1, a defect, evidence, `old` and `new`
- **THEN** `parse_request` returns a request with that kind, group and text

#### Scenario: Text follows the block
- **WHEN** a sentence follows the `plan-request` block in the last message
- **THEN** `parse_request` returns no request

#### Scenario: A key or a kind that does not exist
- **WHEN** the block holds the kind `rewrite`, or an extra key `spec`
- **THEN** `parse_request` returns no request

### Requirement: A path request gives a missing file the name of a tracked file
The job SHALL apply a `path` request only when `old` is a code span of the group, is no tracked file and is not marked `(new)` in the `Changes:` line, and `new` is a tracked file with the same file name. It SHALL replace `old` by `new` in every code span of the text of the group.

#### Scenario: A test that lives in another folder
- **WHEN** group 1 names `tests/commands/test_sample.py`, which is no file, and `tests/roadmap/test_sample.py` is a tracked file
- **THEN** the text of group 1 names `tests/roadmap/test_sample.py` in every code span, and the text of the other groups is the same as before

#### Scenario: Another file name
- **WHEN** `new` is the tracked file `tests/roadmap/test_other.py` and `old` is `tests/commands/test_sample.py`
- **THEN** the job applies nothing and the reason names the rule of the file name

#### Scenario: A path that exists or is new
- **WHEN** `old` is a tracked file, or `old` is marked `(new)` in the `Changes:` line, or `new` exists only as an untracked file
- **THEN** the job applies nothing

### Requirement: A command request keeps the paths of the command
The job SHALL apply a `command` request only when `old` is a verification command of the group, `new` starts with `uv run devops` as whole words, the first word of `new` is a program that a step may run, and the paths in `new` are those of `old` in the same order. It SHALL replace `old` by `new` in the text of the group.

#### Scenario: The same test with the project command
- **WHEN** `old` is `uv run pytest tests/roadmap/test_sample.py` and `new` is `uv run devops ci test tests/roadmap/test_sample.py`
- **THEN** the text of the group holds `new` in the place of `old`

#### Scenario: A command that drops a path
- **WHEN** `new` is `uv run devops docs check`, and `old` names a test file
- **THEN** the job applies nothing and the reason says that the paths differ

#### Scenario: A program outside the list
- **WHEN** `new` starts with `! git grep`, or with `python`
- **THEN** the job applies nothing

### Requirement: A task request adds one unticked task
The job SHALL apply a `task` request by adding one unticked task at the end of the group, numbered after the last task of the group, with `new` as its text and, when `verify` is given, `verify` as its `Verification:` line. `verify` follows the rule of `new` in a command request.

#### Scenario: A missing task
- **WHEN** group 2 has tasks 2.1 and 2.2, and the request gives the text of a task and `verify`
- **THEN** the group holds the unticked task `2.3` with a `Verification:` line, and tasks 2.1 and 2.2 are as before

### Requirement: An amendment changes only the text of a group that is not done
An amendment SHALL change only the text of a group of `tasks.md` that has an unticked task, and the section `## Amendments`. It SHALL NOT change `proposal.md`, `design.md`, a file under `specs/`, the section `## Criteria`, a ticked task or a file outside the change folder.

#### Scenario: A group that is done
- **WHEN** the request names group 1, and every task of group 1 is ticked
- **THEN** the job applies nothing

#### Scenario: A text that only a criterion holds
- **WHEN** `old` is a code span that occurs in the section `## Criteria` and in no group
- **THEN** the job applies nothing, and the section `## Criteria` is as before

### Requirement: Each amendment is a bullet of the section Amendments
The job SHALL add one plain bullet to the section `## Amendments` of `tasks.md` for each applied amendment, before `## Workflow follow-up`, with the group, the kind, the defect, the evidence, and the old and the new text. It SHALL make the section when it is absent. It SHALL mask secrets in the text of the agent, put it on one line and cut it to `CONST_ROADMAP_IMPLEMENT_REASON_CHARS` characters.

#### Scenario: The first amendment
- **WHEN** the job applies a `path` request and the file has no section `## Amendments`
- **THEN** the file has the section before `## Workflow follow-up`, with one bullet that holds the group, the kind, the defect, the evidence, `old` and `new`, and the bullet has no checkbox

#### Scenario: A secret in the evidence
- **WHEN** the evidence of a request holds a token
- **THEN** the bullet holds the masked text

### Requirement: A scope change and a refused request wait for a person
A `scope` request, and any request that breaks a rule of this capability, SHALL change no file. The job SHALL stop the item with the class `plan_defect` and the action left `wait`, and the comment on the issue SHALL be a question that quotes the request.

#### Scenario: A change of a requirement
- **WHEN** a step ends with a `scope` request whose defect says that a requirement of the spec is wrong
- **THEN** `tasks.md` is as before, the item is Blocked with `implement.failure` `plan_defect`, and the comment on the issue quotes the defect and the evidence

#### Scenario: A refused path request
- **WHEN** a `path` request names a `new` file with another file name
- **THEN** the item is stopped as above and the comment gives the rule that the request broke
