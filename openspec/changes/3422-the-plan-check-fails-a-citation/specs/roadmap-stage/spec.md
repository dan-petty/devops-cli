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

#### Scenario: The replay passes no reader
- **WHEN** `check_proposal` runs with no `read_text` callable and the plan holds a stale citation.
- **THEN** `check_proposal` returns no problem for that citation.

### Requirement: Compare a citation with collapsed white space
The plan check SHALL compare the cited text with the staged line after it collapses white space in both.

#### Scenario: The spacing differs
- **WHEN** `feasibility` holds `src/sample.py:4:def f():` and line 4 holds `def f():`.
- **THEN** `check_proposal` returns no problem that names `src/sample.py`.

### Requirement: The staged tree reads the text of a cited file
`StagedTree` SHALL return the text of a tracked file of its checkout, and MUST return `None` when it holds no checkout or the file is absent.

#### Scenario: The tree holds the checkout
- **WHEN** the tree is built from a checkout that holds `src/sample.py`, and a caller asks for its text.
- **THEN** the reply holds the lines of `src/sample.py` at that commit.

#### Scenario: The tree holds no checkout
- **WHEN** the tree is built from a list of paths, as the replay builds it, and a caller asks for the text of `src/sample.py`.
- **THEN** the reply is `None`.

### Requirement: The stage prompt prefers a symbol citation
The stage prompt MUST tell the planner to cite a symbol instead of a line number when a line is not needed.

#### Scenario: The prompt states the symbol form
- **WHEN** a test reads `src/devops_cli/ai/tasks/roadmap_stage_change.md`.
- **THEN** the text holds the `path:def name` form and the instruction to prefer it.
