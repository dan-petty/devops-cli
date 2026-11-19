# Spec Delta

## ADDED Requirements

### Requirement: Relative clause read
The trace gate SHALL not judge the last path before a relative-clause read whose object holds no path.

#### Scenario: Relative clause with a planner read
- **WHEN** the trace holds the tool `read_file` and `src/devops_cli/sample.py`, and the feasibility section says `` `read_file` of `src/devops_cli/sample.py` showed that `_create` fetches `origin/main`, so the branch can start past the commit that the planner read. ``
- **THEN** `check_proposal` returns no trace problem.

### Requirement: Code subject before a parenthesis
The trace gate SHALL not treat a code subject with a file citation in parentheses as a read by the run.

#### Scenario: Code subject with a citation in parentheses
- **WHEN** the trace holds `src/devops_cli/sample.py` and the feasibility section says `` `collect_context` (`src/devops_cli/sample.py`) reads `CONTEXT.md` and a tree. ``
- **THEN** `check_proposal` returns no trace problem.

### Requirement: Code subject of code spans only
The trace gate SHALL recognize a list of code spans as a code subject before a read verb.

#### Scenario: Code subject of multiple code spans
- **WHEN** the trace holds `src/devops_cli/sample.py` and the feasibility section says `` `src/devops_cli/sample.py:107` and `src/b.py:436` read `_core_v1`. ``
- **THEN** `check_proposal` returns no trace problem.

### Requirement: Negation includes cannot
The trace gate SHALL treat `cannot` as a negation word in read claims.

#### Scenario: Negation includes cannot
- **WHEN** the trace holds no path and the feasibility section says `` `/proc/self/exe` cannot be read. ``
- **THEN** `check_proposal` returns no trace problem.

### Requirement: Trailing line ranges stripped from citations
The trace gate SHALL strip trailing ` <start>-<end>` line ranges from path citations.

#### Scenario: Citation with trailing line range
- **WHEN** the trace holds `src/devops_cli/sample.py` and the feasibility section says `` I read `src/devops_cli/sample.py 590-610` and found the function. ``
- **THEN** `check_proposal` returns no trace problem.
