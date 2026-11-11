## MODIFIED Requirements

### Requirement: The path gate names every caller of a function that a task changes
The path gate SHALL refuse a plan whose task clause adds a parameter, an argument or a keyword to a function, and that leaves out a file under `src/` that calls the function. A clause ends at a `.`, a `:` or a `;` outside a code span. A name that no module under `src/` defines with `def` is no function, and a call is a call of the name itself, as `ast` reads it.

#### Scenario: A task adds a parameter to a function
- **WHEN** A task text of a group holds the words Add a probes parameter to `check_proposal`
- **THEN** The caller check reads the function name `check_proposal`

#### Scenario: A task adds an argument to two functions
- **WHEN** A task text holds the words add the keyword-only argument `base_scenarios` to `check_gates` and `check_proposal`
- **THEN** The caller check reads the function names `check_gates` and `check_proposal`

#### Scenario: A task adds a member to a class
- **WHEN** A task text holds the words Add `REVIEW = "review"` to `FailureClass`, or Add the property `added_names` to `TaskGroup`
- **THEN** The caller check reads no function name

#### Scenario: A name in the next clause
- **WHEN** A task text holds the words Add the method `_repair_scope` to the run: it takes the folder, and pass the same log to `_fix`
- **THEN** The caller check reads no function name

#### Scenario: Two files call the function
- **WHEN** The checkout holds `src/a.py` and `src/b.py`, each calls `check_proposal`, and a module defines it with `def`
- **THEN** The caller search returns `src/a.py` and `src/b.py`

#### Scenario: A longer name and a string are no call
- **WHEN** A file holds `scan_fix(log)` and a docstring that holds `_fix(log)`
- **THEN** The caller search for `_fix` does not return that file

#### Scenario: A class has no caller
- **WHEN** The function name is the name of a class, as `TaskGroup` is, and a file calls `asyncio.TaskGroup()`
- **THEN** The caller search returns no file

#### Scenario: The plan omits a caller file
- **WHEN** A plan changes `check_proposal` and its `changes` lists hold `src/devops_cli/roadmap/stage_eval_gates.py` and no `src/devops_cli/roadmap/stage.py`
- **THEN** `path_problems` returns a problem that names `check_proposal` and `src/devops_cli/roadmap/stage.py`

#### Scenario: The plan lists every caller file
- **WHEN** A plan changes `check_proposal` and its `changes` lists hold every file that the caller search returns
- **THEN** `path_problems` returns no problem about a caller of `check_proposal`

#### Scenario: The tree holds no checkout
- **WHEN** The path gate runs on a tree of a replay case, which holds no checkout
- **THEN** `path_problems` returns no problem about a caller

### Requirement: Refuse a behavior group that omits the test of its module
The stage plan validation SHALL refuse a behavior group that changes an existing Python module under `src/` and names no test file of the staged tree that imports that module, imports a package whose `__init__.py` imports it, or imports another module that the plan changes and that imports it.

#### Scenario: A source change names only a new test
- **WHEN** a behavior group changes `src/devops_cli/roadmap/stage/stage_paths.py` and names only the test file it creates, while `tests/roadmap/stage/test_roadmap_stage_paths.py` imports that module
- **THEN** `existing_test_problems` returns one problem that names the group, the module and that test

### Requirement: Accept a behavior group that names the test of its module
The stage plan validation SHALL accept a behavior group that changes an existing Python module under `src/` and names at least one test file of the staged tree that imports that module, imports a package whose `__init__.py` imports it, or imports another module that the plan changes and that imports it.

#### Scenario: The named test imports the module and its file name differs from the module name
- **WHEN** a behavior group changes `src/devops_cli/roadmap/stage/stage_paths.py` and lists `tests/roadmap/stage/test_roadmap_stage_paths.py` in its `reads`
- **THEN** `existing_test_problems` returns no problem for that group

#### Scenario: The named test imports the package of the messages
- **WHEN** a behavior group changes `src/devops_cli/lang/en/messages.py` and reads a test that holds `from devops_cli.lang import MESSAGES`
- **THEN** `existing_test_problems` returns no problem for that group

#### Scenario: The named test runs the messages through a changed module
- **WHEN** a behavior group changes `src/devops_cli/roadmap/follow.py`, which imports the messages, and `src/devops_cli/lang/en/messages.py`, and reads the test that imports `devops_cli.roadmap.follow`
- **THEN** `existing_test_problems` returns no problem for that group

### Requirement: Exempt a module that has no existing test
The stage plan validation SHALL accept a behavior group that changes an existing Python module under `src/` when the staged tree holds no test file that imports that module, a package whose `__init__.py` imports it, or another module that the plan changes and that imports it.

#### Scenario: An existing module has no existing test
- **WHEN** a behavior group changes a module of `src/` and the staged tree holds no test file of that module
- **THEN** `existing_test_problems` returns no problem for that group

## ADDED Requirements

### Requirement: A test that holds the name of a module in text is no test of it
The stage plan validation SHALL NOT count a test file as a test of a module when the test holds the path or the dotted name of the module only in a string, in a comment or in an import for types only.

#### Scenario: The scaffold test holds the path of the messages module
- **WHEN** a behavior group changes `src/devops_cli/lang/en/messages.py`, and `tests/commands/test_new.py` holds the string `src/devops_cli/lang/en/messages.py` and imports no module of `devops_cli.lang`
- **THEN** `record_module_tests` does not name `tests/commands/test_new.py` for that module

#### Scenario: The search reads a dotted name as fixed text
- **WHEN** `grep_at` searches for `devops_cli.lang.en.messages`, and one test holds that dotted name while another holds only the path `src/devops_cli/lang/en/messages.py`
- **THEN** `grep_at` returns only the test that holds the dotted name
