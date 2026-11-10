## ADDED Requirements

### Requirement: Code that reads a file is no claim of the run
The stage job SHALL NOT take `reads` or `reading` as a claim that the run read a path when a code span, `it` or `which` is its subject. It SHALL still refuse a claim of the run or of the author, such as `I read` or `the run read`, when the plan runs hold no call for the path.

#### Scenario: A function reads a file
- **WHEN** the trace holds no call and the feasibility section says `because it reads `.github/labels.yml` of the default branch`.
- **THEN** `check_proposal` returns no trace problem.

#### Scenario: The author reads a file
- **WHEN** the trace holds no call and the feasibility section says `I read `src/x.py` and found the function`.
- **THEN** `check_proposal` returns a problem that names `src/x.py`.
