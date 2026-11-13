## MODIFIED Requirements

### Requirement: The trace gate reads the path of each citation form
The stage job SHALL judge a Feasibility read claim by the path of its code span: the path of a `path:N`, `path:N-M`, `path:N:text` or `path:def name` citation, without a toolbox tool name before it, the start and end line after the path of that form (`read_file path 50 215`), a leading `./` or a trailing `/`. It SHALL remove each sentence of the probe lines that the plan quotes before it reads the claim. It SHALL still refuse a claim of a path that the plan runs did not read, and name that path.

#### Scenario: A line range of a read file
- **WHEN** the trace holds a `read_file` call for `src/x.py` and the feasibility section says `the run read `src/x.py:10-20``.
- **THEN** `check_proposal` returns no trace problem.

#### Scenario: A tool name before a read path
- **WHEN** the trace holds a `read_file` call for `src/x.py` and the feasibility section says `the run read `read_file src/x.py``.
- **THEN** `check_proposal` returns no trace problem.

#### Scenario: A read path with its start and end line
- **WHEN** the trace holds a `read_file` call for `src/x.py` and the feasibility section says `` `read_file src/x.py 50 215` confirms the gap. ``
- **THEN** `check_proposal` returns no trace problem.

#### Scenario: An unread path with its start and end line
- **WHEN** the trace holds a `read_file` call for `src/x.py` and the feasibility section says `` `read_file src/y.py 50 215` confirms the gap. ``
- **THEN** `check_proposal` returns a problem that names `src/y.py` without the line numbers.

#### Scenario: A listed directory with a trailing slash
- **WHEN** the trace holds a `list_files` call for the directory `tests/telemetry` and the feasibility section says `the run read `tests/telemetry/``.
- **THEN** `check_proposal` returns no trace problem.

#### Scenario: A line range of an unread file
- **WHEN** the trace holds a `read_file` call for `src/x.py` and the feasibility section says `the run read `src/y.py:10-20``.
- **THEN** `check_proposal` returns a problem that names `src/y.py`.

#### Scenario: A quoted probe line
- **WHEN** the trace holds no call, the probe lines hold `The path `src/x.py` is a file of the staging commit.`, and the feasibility section says `The probe line reads: The path `src/x.py` is a file of the staging commit.`
- **THEN** `check_proposal` returns no trace problem.
