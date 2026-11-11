## ADDED Requirements

### Requirement: The trace gate reads the subject and the object of a read word
The stage job SHALL take a read word as a claim of the run only when it is `read_file`, a passive, a read with no subject, or a read whose subject names the run or its author. A read whose subject is the plan, a group, the probe or code, and `read` in `read-only`, SHALL be no claim. The gate SHALL judge the path that the read takes: the first path after it in its clause, the subject of a passive, or else the last path before it.

#### Scenario: The plan is the subject
- **WHEN** the trace holds no path and the feasibility section says `This plan reads `tests/x.py` in group 2.`
- **THEN** `check_proposal` returns no trace problem.

#### Scenario: A read-only root
- **WHEN** the trace holds no path and the feasibility section says `` `k8s/x.yaml` runs the pod with a read-only root. ``
- **THEN** `check_proposal` returns no trace problem.

#### Scenario: A path in another clause
- **WHEN** the trace holds the tools `read_file` and `search_code` and no path, and the feasibility section says `` `read_file` of that prompt shows the rule, and `search_code` returned one hit in `src/tf.py`. ``
- **THEN** `check_proposal` returns no trace problem.

#### Scenario: A claim of the run
- **WHEN** the trace holds no path and the feasibility section says `I read `src/missing.py` and found the function.`
- **THEN** `check_proposal` returns a problem that names `src/missing.py`.

#### Scenario: A passive read
- **WHEN** the trace holds no path and the feasibility section says `` `src/missing.py` was read on the base. ``
- **THEN** `check_proposal` returns a problem that names `src/missing.py`.

### Requirement: A search match supports a citation of its line
`TraceFacts.of` SHALL hold the `path:line` of each match line of a `search_code` or `callers` answer, and the kept plan file SHALL hold those that its Feasibility section cites. The trace gate SHALL accept a read claim of a `path:line` or `path:line:text` citation of such a line. It SHALL still refuse a claim of the whole file, of another line or of a line range, and it SHALL give a path of a probe line no support.

#### Scenario: A search answer
- **WHEN** a `search_code` call of a plan run gets the answer `tests/a.py:5:import x`
- **THEN** `TraceFacts.of` holds the line `tests/a.py:5`.

#### Scenario: A citation of a match line
- **WHEN** the trace holds the match line `tests/a.py:5` and no path, and the feasibility section says `The run read `tests/a.py:5:import x`.`
- **THEN** `check_proposal` returns no trace problem.

#### Scenario: A claim of the whole file
- **WHEN** the trace holds the match line `tests/a.py:5` and no path, and the feasibility section says `The run read `tests/a.py`.`
- **THEN** `check_proposal` returns a problem that names `tests/a.py`.
