## ADDED Requirements

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
