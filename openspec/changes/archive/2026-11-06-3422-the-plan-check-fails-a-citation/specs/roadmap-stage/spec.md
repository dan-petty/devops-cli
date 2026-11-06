## ADDED Requirements

### Requirement: Refuse a stale line citation
The plan check SHALL refuse a `path:line:text` citation when the cited line of the staged file does not hold the cited text.

#### Scenario: The line holds another text
- **WHEN** `feasibility` holds `src/sample.py:4:def f():` and line 4 of the staged `src/sample.py` holds `def g():`.
- **THEN** `check_proposal` returns a problem that names `feasibility` and `src/sample.py`.

### Requirement: Accept a true line citation
The plan check SHALL accept a `path:line:text` citation when the cited line of the staged file holds the cited text.

#### Scenario: The line holds the cited text
- **WHEN** `feasibility` holds `src/sample.py:4:def f():` and line 4 of the staged `src/sample.py` holds `def f():`.
- **THEN** `check_proposal` returns no problem that names `src/sample.py`.

### Requirement: Refuse a citation of an absent line
The plan check MUST refuse a citation when the reader returns no such path or the file holds no such line.

#### Scenario: The line number is past the end of the file
- **WHEN** `feasibility` holds `src/sample.py:99:def f():` and the reader returns the 10 lines of `src/sample.py`.
- **THEN** `check_proposal` returns a problem that names `feasibility` and `src/sample.py`.

### Requirement: Resolve a symbol citation
The plan check SHALL accept a `path:def name` or a `path:class name` citation when the staged file defines the symbol at any line.

#### Scenario: The definition moved
- **WHEN** `feasibility` holds `src/sample.py:def f` and the staged `src/sample.py` defines `def f(` at line 7.
- **THEN** `check_proposal` returns no problem that names `src/sample.py`.

### Requirement: Refuse an absent symbol
The plan check MUST refuse a symbol citation when the staged file holds no definition of the symbol.

#### Scenario: The file defines another symbol
- **WHEN** `feasibility` holds `src/sample.py:def f` and the staged `src/sample.py` defines only `def g(`.
- **THEN** `check_proposal` returns a problem that names `feasibility` and `src/sample.py`.

### Requirement: Scan the three evidence fields
The plan check SHALL scan `feasibility`, `why` and each line of `what_changes` for citations.

#### Scenario: A stale citation sits in what_changes
- **WHEN** a line of `what_changes` holds a citation of a line that holds other text.
- **THEN** `check_proposal` returns a problem that names `what_changes` and the cited path.

### Requirement: Judge no citation without file text
The plan check SHALL judge no citation when it holds no reader of the staged files.

#### Scenario: The check holds no reader
- **WHEN** `check_proposal` runs with no `read_text` callable and the plan holds a stale citation.
- **THEN** `check_proposal` returns no problem for that citation.

### Requirement: Compare a citation with collapsed white space
The plan check SHALL compare the cited text with the staged line after it collapses white space in both.

#### Scenario: The spacing differs
- **WHEN** `feasibility` holds `src/sample.py:4:def f():` and line 4 holds `def f():`.
- **THEN** `check_proposal` returns no problem that names `src/sample.py`.

### Requirement: The stage job reads the text of a cited file at the staged commit
The stage job SHALL pass `check_proposal` a reader that returns the text of a cited file at the staged commit, and the replay MUST pass no reader.

#### Scenario: The job holds the checkout and the commit
- **WHEN** the stage job holds the checkout and the staged commit, and a plan cites `src/sample.py`, and the reader is asked for its text.
- **THEN** the reply holds the lines of `src/sample.py` at that commit.

#### Scenario: The replay passes no reader
- **WHEN** the replay of the golden set calls `check_proposal` with no reader, and a plan cites `src/sample.py`.
- **THEN** the check judges no citation.

### Requirement: The stage prompt prefers a symbol citation
The stage prompt MUST tell the planner to cite a symbol instead of a line number when a line is not needed.

#### Scenario: The prompt states the symbol form
- **WHEN** a test reads `src/devops_cli/ai/tasks/roadmap_stage_change.md`.
- **THEN** the text holds the `path:def name` form and the instruction to prefer it.
