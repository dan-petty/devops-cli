## ADDED Requirements

### Requirement: The type check of a step is the type check of the gate
The step SHALL run `mypy` on the changed Python files under the paths of the type check of `devops ci`, with the options of that check. It SHALL take the paths and the options from the same definition as the row `typecheck` of `devops ci`. It SHALL run no type check on a changed file outside those paths, and no `mypy` when no changed file is inside them. It SHALL run `ruff check` and `ruff format` on every changed Python file.

#### Scenario: A test file with old type errors
- **WHEN** the model changes a test file that has type errors of its own, `mypy` would fail on that file, and the other exit checks pass
- **THEN** the step reports done, no `mypy` command ran, and `ruff check` ran on the test file

#### Scenario: A source file with a new type error
- **WHEN** the model changes a file under `src/` and a test file, and `mypy` fails on the source file
- **THEN** the command of `mypy` names only the source file, and the step runs its one extra turn with the text of the failure

#### Scenario: The step and the gate agree
- **WHEN** the step type-checks a file under each path of the gate
- **THEN** the command line of the step is the command line of the row `typecheck` with the files in place of the paths
