## MODIFIED Requirements

### Requirement: Feasibility cites only what the plan run did
The stage job SHALL refuse a feasibility line that names a toolbox tool, or states that a code-span path was read, when the plan runs of the item hold no call that supports it, and SHALL accept a line that negates the claim.

#### Scenario: A read claim with no tool call
- **WHEN** The trace holds zero calls and the feasibility section says `read `src/x.py``.
- **THEN** `check_proposal` returns a problem that names `src/x.py` and the absent read.

#### Scenario: A read claim that the trace supports
- **WHEN** The trace holds a `read_file` call for `src/x.py` and the feasibility section says `read `src/x.py``.
- **THEN** `check_proposal` returns no problem for that line.

#### Scenario: A tool name that the trace lacks
- **WHEN** The trace holds no `search_code` call and the feasibility section says `search_code` returned a result.
- **THEN** `check_proposal` returns a problem that names `search_code`.

#### Scenario: A stated gap
- **WHEN** The trace holds zero calls and the feasibility section says `not read `src/x.py``.
- **THEN** `check_proposal` returns no problem for that line.

#### Scenario: A caller with no run
- **WHEN** `check_proposal` gets no trace facts and the feasibility section says `read `src/x.py``.
- **THEN** `check_proposal` returns no trace problem, and its other checks run as before.

#### Scenario: A claim of the first run after a return
- **WHEN** The first plan run called `read_file` for `src/x.py`, its reply was returned for another problem, the second plan run called no tool, and the second reply says `read `src/x.py``.
- **THEN** The second reply passes the trace gate.

### Requirement: Trace facts of a run
`TraceFacts.of` SHALL hold the tool name of each call of a `RunTrace` and the `path`, `directory` and `paths` values of an argument that parses as JSON, and the stage job SHALL pass to `check_proposal` the facts of the combined trace of every plan run of the item so far. A review run SHALL NOT be a plan run.

#### Scenario: A trace with two calls
- **WHEN** The trace holds a `read_file` call for `src/x.py` and a `search_code` call for `needle`.
- **THEN** The facts hold the tools `read_file` and `search_code`, and the path `src/x.py`.

#### Scenario: The stage job calls the check
- **WHEN** The planner gets a reply from a toolbox run that called `read_file` for `src/x.py`.
- **THEN** The `check_proposal` call for that reply holds the facts with the tool `read_file` and the path `src/x.py`.

#### Scenario: The facts hold every plan run
- **WHEN** The first plan run called `read_file` for `src/x.py` and the second plan run called no tool.
- **THEN** The facts hold the tool `read_file` and the path `src/x.py`.

#### Scenario: A review run supports no claim
- **WHEN** A review run called `read_file` for `src/x.py` and no plan run called it.
- **THEN** The facts hold no tool and no path.
