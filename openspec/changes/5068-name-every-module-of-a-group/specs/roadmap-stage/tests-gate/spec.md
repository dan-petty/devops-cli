## RENAMED Requirements

- FROM: `### Requirement: Report one problem for each group that omits its test`
- TO: `### Requirement: Report one problem for each module whose test a group omits`

## MODIFIED Requirements

### Requirement: Report one problem for each module whose test a group omits
The stage plan validation SHALL report one problem for each module that a behavior group changes and whose existing test files the group names nowhere, for every module of the group in one result, so that one repair can name every test. A test that the problem of an earlier module of the group asks for SHALL count as named for each later module of that group, so that the stage plan validation asks for no second test of a module that the asked test already runs. The stage plan validation SHALL accept the group only when it reports no problem for it.

#### Scenario: Two groups omit their existing tests
- **WHEN** two behavior groups each change an existing module of `src/` and name no existing test of it
- **THEN** `existing_test_problems` returns one problem for each group

#### Scenario: One group omits the tests of two modules
- **WHEN** a behavior group changes `src/devops_cli/roadmap/step_files.py` and `src/devops_cli/roadmap/follow.py`, each with its own existing test, and names neither test
- **THEN** `existing_test_problems` returns two problems: one that names `step_files.py` and its test, and one that names `follow.py` and its test

#### Scenario: The group names the test of the first module only
- **WHEN** a behavior group changes two modules with their own tests and names only the test of the first module
- **THEN** `existing_test_problems` returns one problem, and it names the second module and its test

#### Scenario: One asked test also runs a later module
- **WHEN** a behavior group changes two modules, names no test of either, and the test that the problem of the first module asks for is also a test of the second module
- **THEN** `existing_test_problems` returns one problem for the first module, and the group that also names that test gets no problem
