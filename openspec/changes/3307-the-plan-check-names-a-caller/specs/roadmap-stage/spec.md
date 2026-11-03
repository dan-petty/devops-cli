## ADDED Requirements

### Requirement: The path gate names every caller of a function that a task changes
The path gate SHALL refuse a plan that adds a parameter to a function and leaves out a file under `src/` that calls the function.

#### Scenario: A task adds a parameter to a function
- **WHEN** A task text of a group holds the words Add a probes parameter to `check_proposal`
- **THEN** The caller check reads the function name `check_proposal`

#### Scenario: Two files call the function
- **WHEN** The checkout holds `src/a.py` and `src/b.py`, and each holds `check_proposal(`
- **THEN** The caller search returns `src/a.py` and `src/b.py`

#### Scenario: The plan omits a caller file
- **WHEN** A plan changes `check_proposal` and its `changes` lists hold `src/devops_cli/roadmap/stage_eval_gates.py` and no `src/devops_cli/roadmap/stage.py`
- **THEN** `path_problems` returns a problem that names `check_proposal` and `src/devops_cli/roadmap/stage.py`

#### Scenario: The plan lists every caller file
- **WHEN** A plan changes `check_proposal` and its `changes` lists hold every file that the caller search returns
- **THEN** `path_problems` returns no problem about a caller of `check_proposal`

#### Scenario: The tree holds no checkout
- **WHEN** The path gate runs on a tree of a replay case, which holds no checkout
- **THEN** `path_problems` returns no problem about a caller
