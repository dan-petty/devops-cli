## ADDED Requirements

### Requirement: The trace gate reads the path of a tool call citation
The Feasibility trace gate SHALL take the first quoted argument of a call to a stage tool, such as `read_file("src/a.py", 60, 80)`, as the claimed path, with double or single quotes. It SHALL apply the rules of the `path:line` form and of a leading `./` to it. A call of a word that is no stage tool SHALL stay whole.

#### Scenario: A double-quoted call of a read path
- **WHEN** a Feasibility line cites `read_file("src/devops_cli/sample.py", 60, 80)` and the trace holds `read_file` and that path
- **THEN** `check_proposal` returns no trace-path problem

#### Scenario: A single-quoted call of a read path
- **WHEN** a Feasibility line cites `read_file('src/devops_cli/sample.py', 60, 80)` and the trace holds `read_file` and that path
- **THEN** `check_proposal` returns no trace-path problem

#### Scenario: A call of an unread path
- **WHEN** a Feasibility line cites `read_file("src/devops_cli/other.py", 60, 80)` and the trace holds no such path
- **THEN** `check_proposal` returns one problem that names `src/devops_cli/other.py`

#### Scenario: A call of a word that is no stage tool
- **WHEN** a Feasibility line cites `cat("src/devops_cli/sample.py")`
- **THEN** the claimed path is the whole span and the gate refuses it

#### Scenario: The space form keeps its result
- **WHEN** a Feasibility line cites `read_file src/devops_cli/sample.py` and the trace holds that path
- **THEN** `check_proposal` returns no trace-path problem
