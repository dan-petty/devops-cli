## ADDED Requirements

### Requirement: The trace gate judges the path of a citation
The stage job SHALL judge the path of a code span in the form `path:line:text` or `path:def name` when it checks a claim that the run read a file, and SHALL accept the claim when a path that the run read equals that path or ends with it after a `/`. It SHALL read the verbs of a feasibility sentence outside its code spans, except a span that names a toolbox tool. The problem of an unread path SHALL name the path alone.

#### Scenario: A symbol citation of a read file
- **WHEN** the trace holds a `read_file` call for `src/x.py` and the feasibility section says `read `src/x.py:def load``.
- **THEN** `check_proposal` returns no problem for that line.

#### Scenario: A line citation of an unread file
- **WHEN** the trace holds a `read_file` call for `src/x.py` and the feasibility section says `read `src/y.py:12:value = 1``.
- **THEN** `check_proposal` returns a problem that names `src/y.py` and not `value = 1`.

#### Scenario: A file named by its name
- **WHEN** the trace holds a `read_file` call for `src/config/constants.py` and the feasibility section says `read `constants.py``.
- **THEN** `check_proposal` returns no problem for that line.

#### Scenario: A word of reading inside a quoted line
- **WHEN** the trace holds no call and the feasibility section quotes `src/x.py:3:(("ai", "read"), 60.0)` with no verb of reading outside the code span.
- **THEN** `check_proposal` returns no problem for that line.
