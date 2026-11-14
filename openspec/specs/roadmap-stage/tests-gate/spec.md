# roadmap-stage/tests-gate Specification

## Purpose
The test rules of a plan: the project form of a verify command, the mirror test path, the test that a behavior group names, and the nearest test of a module.

## Requirements

### Requirement: A verify command has the project form
`check_proposal` SHALL refuse a group whose `verify` command does not start with `uv run devops` as a whole word, unless it is a negative search. It SHALL refuse a `verify` command of the project form that the implement step refuses to run, and the problem SHALL hold the reason of the step. The reason SHALL come from the table that the step reads, so that the gate and the step cannot differ.

#### Scenario: A pytest verify command is refused
- **WHEN** a group gives the `verify` command `uv run pytest tests/roadmap/test_stage.py`
- **THEN** `check_proposal` returns a problem that names the command and the accepted forms

#### Scenario: A devops command or a negative search is accepted
- **WHEN** a group gives the `verify` command `uv run devops ci test tests/roadmap/test_stage.py` or `! git grep -n old_name src/ tests/`
- **THEN** `check_proposal` returns no problem about the `verify` command

#### Scenario: A negative search that the step refuses
- **WHEN** a group gives the `verify` command `! git grep -n name src/ | cat` or `! git grep -O name src/`
- **THEN** `check_proposal` returns a problem that names the command and the reason that the step gives

#### Scenario: A verify command that the step runs
- **WHEN** a group gives any of the commands `uv run devops ci`, `uv run devops docs check`, `! git grep -n absent_name src/ tests/` and `! git grep -nI -F old_name -- src/ tests/`
- **THEN** `check_proposal` returns no problem, and the step runs each of them

### Requirement: A new test module sits in a mirror directory
`check_proposal` SHALL refuse a path in `creates` that is a test module under `tests/` unless it is in `tests/invariants/` or in the directory that mirrors the package of a source file that the plan changes.

#### Scenario: A flat test path is refused
- **WHEN** a group creates `tests/test_stage.py` and the plan changes `src/devops_cli/roadmap/stage/stage.py`
- **THEN** `check_proposal` returns a problem that names the path and the directory `tests/roadmap`

#### Scenario: A mirrored or an invariant test path is accepted
- **WHEN** a group creates `tests/roadmap/test_stage.py` or `tests/invariants/test_source_tree.py`
- **THEN** `check_proposal` returns no problem about the test path

### Requirement: The prompt and the rules give a mirrored test path
The stage prompt and `openspec/config.yaml` SHALL give only example test paths whose folder under `tests/` mirrors a package of `src/devops_cli/`.

#### Scenario: Every example path is mirrored
- **WHEN** a test reads the stage prompt and `openspec/config.yaml`
- **THEN** each example test path has a folder under `tests/` that mirrors a package of `src/devops_cli/`

### Requirement: A manifest plan names the tests that reference it
The stage job SHALL refuse a plan that changes a YAML manifest under `k8s/` and lists no test file that references that manifest, because the implement job cannot edit a test outside the `Changes:` list of the plan.

#### Scenario: The plan of the logging egress rule omits the logging test
- **WHEN** the plan changes `k8s/logging/networkpolicy.yaml`, the job records `tests/commands/k8s/test_k8s_logging_stack.py` as a reference to it, and the plan lists no such test
- **THEN** the problem names `k8s/logging/networkpolicy.yaml` and `tests/commands/k8s/test_k8s_logging_stack.py`, and it asks for the test in `Changes:`

#### Scenario: The plan of the logging egress rule names the logging test
- **WHEN** the plan changes `k8s/logging/networkpolicy.yaml` and lists `tests/commands/k8s/test_k8s_logging_stack.py`
- **THEN** the path gate reports no problem that names either path

#### Scenario: The test builds the manifest path from its parts
- **WHEN** a test file holds the literals `logging` and `networkpolicy.yaml` in separate strings
- **THEN** the record names that test as a reference to `k8s/logging/networkpolicy.yaml`

#### Scenario: The test holds only the folder name
- **WHEN** a test file holds `logging` but not `networkpolicy.yaml`
- **THEN** the record names no reference to `k8s/logging/networkpolicy.yaml` for that file

#### Scenario: The job records no reference
- **WHEN** the gate gets no record, as a replay of a case with none does
- **THEN** the check reports no missing reference

### Requirement: A test-only other group names its test function
The stage plan SHALL refuse an other task group that changes only test modules and whose implementation names no test function in a code span. It SHALL accept an other group with one changed path that is no test module. A test module is a path under `tests/` whose base name starts with `test_` and ends with `.py`. A code span names a test function when its text after the last `::`, or the whole span, starts with `test_`, with optional parentheses.

#### Scenario: Conditional test-only group
- **WHEN** `content_problems` reads a proposal with an other group whose `changes` lists only `tests/roadmap/stage/test_roadmap_stage_content.py` and whose `implementation` holds no code span with a `test_` function
- **THEN** the returned problems hold the refusal sentence for that group

#### Scenario: Named test function
- **WHEN** `content_problems` reads a proposal with an other group whose `changes` lists only `tests/roadmap/stage/test_roadmap_stage_content.py` and whose `implementation` holds a code span with `test_conditional_group`
- **THEN** the returned problems hold no refusal sentence for that group

#### Scenario: Named test function after a path
- **WHEN** `content_problems` reads a proposal with an other group whose `changes` lists only `tests/roadmap/stage/test_roadmap_stage_content.py` and whose `implementation` holds a code span with `tests/roadmap/stage/test_roadmap_stage_content.py::test_conditional_group`
- **THEN** the returned problems hold no refusal sentence for that group

#### Scenario: Group with a source path
- **WHEN** `content_problems` reads an other group whose `changes` lists `tests/roadmap/stage/test_roadmap_stage_content.py` and `src/devops_cli/roadmap/stage/stage_change.py` and whose `implementation` names no test function
- **THEN** the returned problems hold no refusal sentence for that group

#### Scenario: Refusal names the group
- **WHEN** `content_problems` refuses an other group with the title `Keep the roadmap stage tests green`
- **THEN** the returned sentence holds `Keep the roadmap stage tests green`

#### Scenario: Test helper group
- **WHEN** `content_problems` reads a proposal with an other group whose `changes` lists only `tests/support/builders.py` and whose `implementation` names no test function
- **THEN** the returned problems hold no refusal sentence for that group

#### Scenario: Test file path with no function
- **WHEN** `content_problems` reads a proposal with an other group whose `changes` lists only `tests/roadmap/stage/test_roadmap_stage_content.py` and whose `implementation` holds the code span `tests/roadmap/stage/test_roadmap_stage_content.py` and no other code span
- **THEN** the returned problems hold the refusal sentence for that group

### Requirement: The planner prompt asks for one exact change and its test
The stage prompt SHALL state that a task group gives one exact change and names the failing test that it updates in a code span.

#### Scenario: The stage prompt loads
- **WHEN** the stage job loads `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- **THEN** the prompt text states that a group gives one exact change and names the failing test in a code span

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

### Requirement: Leave out the test files that the plan creates
The stage plan validation MUST leave out every test path that a group lists in `creates`, so that a test file that the plan creates is no existing test.

#### Scenario: The plan creates the only test of a module it also changes
- **WHEN** a behavior group changes an existing module and creates the only test file that imports it
- **THEN** the created test is no existing test, and `existing_test_problems` returns no problem for that group

### Requirement: Report one problem for each module whose test a group omits
The stage plan validation SHALL report one problem for each module that a behavior group changes and whose existing test files the group names nowhere. It SHALL report every such module of the group in one result, so that one repair can name every test.

#### Scenario: Two groups omit their existing tests
- **WHEN** two behavior groups each change an existing module of `src/` and name no existing test of it
- **THEN** `existing_test_problems` returns one problem for each group

#### Scenario: One group omits the tests of two modules
- **WHEN** a behavior group changes `src/devops_cli/roadmap/step_files.py` and `src/devops_cli/roadmap/follow.py`, each with its own existing test, and names neither test
- **THEN** `existing_test_problems` returns two problems: one that names `step_files.py` and its test, and one that names `follow.py` and its test

#### Scenario: The group names the test of the first module only
- **WHEN** a behavior group changes two modules with their own tests and names only the test of the first module
- **THEN** `existing_test_problems` returns one problem, and it names the second module and its test

### Requirement: An asked test counts as named for the later modules of the group
A test that the problem of an earlier module of a behavior group asks for SHALL count as named for each later module of that group, so that the stage plan validation asks for no second test of a module that the asked test already runs. The group SHALL still pass only when it names a test of each module.

#### Scenario: One asked test also runs a later module
- **WHEN** a behavior group changes two modules, names no test of either, and the test that the problem of the first module asks for is also a test of the second module
- **THEN** `existing_test_problems` returns one problem for the first module, and the group that also names that test gets no problem

### Requirement: A test that holds the name of a module in text is no test of it
The stage plan validation SHALL NOT count a test file as a test of a module when the test holds the path or the dotted name of the module only in a string, in a comment or in an import for types only.

#### Scenario: The scaffold test holds the path of the messages module
- **WHEN** a behavior group changes `src/devops_cli/lang/en/messages.py`, and `tests/commands/test_new.py` holds the string `src/devops_cli/lang/en/messages.py` and imports no module of `devops_cli.lang`
- **THEN** `record_module_tests` does not name `tests/commands/test_new.py` for that module

#### Scenario: The search reads a dotted name as fixed text
- **WHEN** `grep_at` searches for `devops_cli.lang.en.messages`, and one test holds that dotted name while another holds only the path `src/devops_cli/lang/en/messages.py`
- **THEN** `grep_at` returns only the test that holds the dotted name

### Requirement: The stale test path problem names the same-name files
The problem of a test path that names no file of the commit SHALL end with the same hint as the missing-path message: the text of `stage_path_same_name` for the files of the staged tree with that file name, or the text of `stage_path_no_same_name` when no file has the name.

#### Scenario: One file has the same name
- **WHEN** a changed docstring names `tests/test_item_grounding.py` and the staged tree holds `tests/github/test_item_grounding.py`
- **THEN** the problem ends with the text of `stage_path_same_name` for `tests/github/test_item_grounding.py`

#### Scenario: No file has the same name
- **WHEN** a changed docstring names `tests/test_absent.py` and no file of the staged tree has the name `test_absent.py`
- **THEN** the problem ends with the text of `stage_path_no_same_name`

### Requirement: The record orders a module's tests nearest first
`record_module_tests` SHALL order the tests of each module by closeness: the mirror test, then a test that imports the dotted name of the module, then a test in the mirror folder, then the rest, each class in path order. It SHALL keep every test that imports the module or an exporting package. A module at the top of the package SHALL have no mirror rank.

#### Scenario: The mirror test comes first
- **WHEN** the record of `src/devops_cli/lang/en/messages.py` holds `tests/lang/en/test_messages.py` and `tests/ai/mcp/test_ai_benchmark_mcp_tool.py`, and both import `devops_cli.lang`
- **THEN** `record_module_tests` returns `tests/lang/en/test_messages.py` first

#### Scenario: A direct import beats a package import
- **WHEN** one test imports `devops_cli.lang.en.messages` and another, first in path order, imports only `devops_cli.lang`
- **THEN** the test that imports the module itself comes first

#### Scenario: Equal tests keep path order
- **WHEN** every test of the record imports `devops_cli.lang` and none is the mirror test
- **THEN** `record_module_tests` returns each test once, in path order

### Requirement: A test of another changed module ranks last
`record_module_tests` SHALL list a test that only another module of the plan imports after every test that imports the changed module itself.

#### Scenario: The module's own test comes first
- **WHEN** a plan changes `stage_paths.py` and `step_files.py`, which imports it, and only the second has a test that imports it
- **THEN** the test of `stage_paths.py` comes first in its record

### Requirement: The problem names the nearest test
`existing_test_problems` SHALL name the first test of the record of the module in the problem sentence, and no later test.

#### Scenario: The problem names the mirror test
- **WHEN** a behavior group changes `src/devops_cli/lang/en/messages.py` and names no test of it, and the record starts with `tests/lang/en/test_messages.py`
- **THEN** the sentence holds `tests/lang/en/test_messages.py` and no other test of the record

### Requirement: A test path in a spec of the plan names a file of the commit
`check_proposal` SHALL fail when a test file path named in a spec of the plan names no file of the commit, and MUST add each such path to its refusal list. It MUST NOT read test paths from the base text of a file that the plan changes, because the plan cannot change that text.

#### Scenario: A spec names a missing test file
- **WHEN** A spec contains `tests/test_missing_example.py` and that file is absent from the commit.
- **THEN** The check reports `tests/test_missing_example.py` as a missing path.

#### Scenario: A base docstring with a missing test path passes
- **WHEN** A plan changes a Python file whose base docstring names `tests/test_x.py`, the commit does not hold that file, and no spec of the plan names it.
- **THEN** `check_proposal` returns no missing test path problem.

#### Scenario: A text that names a test file of the commit passes
- **WHEN** The scanned text names `tests/roadmap/test_roadmap_limit_classes.py` and the commit holds that file.
- **THEN** The check reports no missing path.

### Requirement: A behavior group runs a test module of the group
`form_problems` SHALL refuse a `behavior` group whose `verify` command names no test module, or names a test module that its `test`, `changes`, `creates` and `reads` do not name. A directory under `tests/` SHALL be no test module. A negative search SHALL stay accepted, and a command with a form problem SHALL get the form problem only. The problem SHALL name the group, the command and the test module that the group should run.

#### Scenario: A command that runs no test module
- **WHEN** a behavior group has the verify `uv run devops ci docs` and the test module `tests/test_sample.py`
- **THEN** `form_problems` returns one problem that names the group, the command and `tests/test_sample.py`

#### Scenario: The verify names a test directory
- **WHEN** a behavior group has the verify `uv run devops ci test tests/roadmap/` and the test module `tests/roadmap/test_roadmap_stage_form.py`
- **THEN** `form_problems` returns one problem for that group

#### Scenario: The group runs its own test module
- **WHEN** a behavior group has the verify `uv run devops ci test tests/test_sample.py` and its `test` text names `tests/test_sample.py`
- **THEN** `form_problems` returns no problem for that group

#### Scenario: An other group runs another command
- **WHEN** an `other` group has the verify `uv run devops ci docs`
- **THEN** `form_problems` returns no problem for that group
