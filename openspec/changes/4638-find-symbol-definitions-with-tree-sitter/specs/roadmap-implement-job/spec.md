## MODIFIED Requirements

### Requirement: One shared definition lookup reports a definition at a commit
The stage job, the refine context and the implement job SHALL use `definition_lines` of `src/devops_cli/roadmap/premise.py`. A Python file defines a name with a `def`, a `class` or an assignment line. If no Python file defines it, a file of another language defines it when its tree-sitter grammar finds a symbol of that name. A Markdown file defines nothing. A lookup that reads only some files that name it and finds no definition SHALL be undecided. `defines` reports a list that is not empty.

#### Scenario: Both jobs get the definition lines from one function
- **WHEN** The stage job probes a cited identifier and the implement job checks a task at the same commit
- **THEN** Both jobs get the same definition lines from `definition_lines` of `src/devops_cli/roadmap/premise.py`.

#### Scenario: The check writes nothing
- **WHEN** The implement job checks the tasks of a behavior group at the branch tip
- **THEN** The check runs only read-only git commands and the worktree holds no change.

#### Scenario: A Rust function
- **WHEN** the commit holds `src/scout.rs` with `fn scout_reaches_target() {` on line 4, and `src/main.rs`, which calls the function
- **THEN** `definition_lines` gives only line 4 of `src/scout.rs`

#### Scenario: A shell function
- **WHEN** the commit holds `scripts/deploy.sh` with `setup_node() {` on line 2
- **THEN** `definition_lines` gives line 2 of `scripts/deploy.sh`

#### Scenario: A call and a heading are no definition
- **WHEN** only a Rust call and a Markdown heading name `scout_reaches_target`
- **THEN** `definition_lines` gives no line

#### Scenario: A Python definition costs one command
- **WHEN** a Python file and a Rust file define the name
- **THEN** `definition_lines` gives the Python line and runs one git command

#### Scenario: A cut read that finds no definition is undecided
- **WHEN** 21 Rust files call `shared_helper`, and only `src/z_util.rs`, which is after them in path order, defines it
- **THEN** `definition_lines` gives None, not an empty list
