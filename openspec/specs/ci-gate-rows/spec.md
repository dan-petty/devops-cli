# ci-gate-rows Specification

## Purpose
How `devops ci` checks committed files and the configuration of its tools in rows of its own, so that no pytest test starts ruff, ast-grep or kubectl to read a file, and so that a check runs once for the gate and not once for each pytest worker.

## Requirements

### Requirement: A check of committed files is a row, not a pytest test
The table of `devops ci` SHALL hold a row or a command of a row for each check of committed files or tool configuration that starts a program or parses the whole tree. No pytest test SHALL start ruff, ast-grep, `kubectl kustomize` or a fresh Python interpreter to check a committed file or a configuration.

#### Scenario: The rows are in the table
- **WHEN** the table of checks is read
- **THEN** it holds the rows `k8s`, `test-tree`, `startup-imports` and `swallowed-failures`, each with a command that runs the `main` of one module of `tests/gate`
- **AND** the rows `lint` and `constructs` hold the commands of the Ruff configuration check, `ast-grep test` and the construct gate check

#### Scenario: A row fails on the input that failed its test
- **WHEN** a committed file breaks the check of a row, such as a Ruff complexity cap of 11 or a new blind except in `src`
- **THEN** the command of the row exits 1 and prints the finding

### Requirement: The k8s row renders each application once
The `k8s` row SHALL render each committed kustomization with `kubectl kustomize` once, and every check of the row SHALL read that one render.

#### Scenario: Two checks read one directory
- **WHEN** two checks of the row ask for the render of one committed directory
- **THEN** `kubectl kustomize` runs once for that directory

### Requirement: The startup-import row keeps its budgets and its control
The `startup-imports` row SHALL start each argv in a fresh interpreter under `-X importtime`, SHALL keep the four module limits, and SHALL fail when a run imports a heavy package. It SHALL name the ten slowest imports of a failed run, and it SHALL report the CPU time of its probes.

#### Scenario: The control
- **WHEN** the root help runs after an import of `pydantic_ai`
- **THEN** the probe reports a heavy module and a count over the limit, and the row counts the control as passed

#### Scenario: A failed run
- **WHEN** a help argv imports a heavy module
- **THEN** the finding names the module and lists the ten slowest imports

### Requirement: The startup-import row probes a config with decision modes
The `startup-imports` row SHALL run `devops config get ai.provider` in a fresh interpreter with a config file that sets `roadmap.decisions`, and SHALL fail when that run imports `pydantic_ai` or its settings do not hold the modes of the file.

#### Scenario: A decisions probe that imports pydantic_ai
- **WHEN** the decisions probe prints that `pydantic_ai` is loaded
- **THEN** the row names the probe and its value as a problem

### Requirement: The bwrap row runs the sandbox contract suites where the host can make a sandbox
The table of `devops ci` SHALL hold a row `bwrap` that runs `pytest -m bwrap -n 0` with a bound for each test over the two contract suites of the sandbox, after the host check of the sandbox executor. On a host that fails the check, the row SHALL start no test, SHALL pass, and SHALL show `skipped: <cause>`, also in a cached verdict.

#### Scenario: A host that can make the sandbox
- **WHEN** `devops ci --only bwrap` runs and bubblewrap makes a sandbox on the host
- **THEN** the row starts `uv run pytest -m bwrap -n 0 --timeout=60` with `tests/sandbox/test_host_sandbox.py` and `tests/ai/test_tool_executor_contract.py`

#### Scenario: A host that cannot make the sandbox
- **WHEN** `devops ci --only bwrap` runs and bubblewrap exits 1 with `bwrap: setting up uid map: Permission denied`
- **THEN** the row starts no test, the gate exits 0, and the output shows `[bwrap] skipped: bubblewrap cannot make a sandbox on this host: bwrap: setting up uid map: Permission denied`

#### Scenario: A cached verdict keeps the skip
- **WHEN** a full gate passed with the row skipped, and the gate runs again on the same tree
- **THEN** the cached summary shows the row as skipped and starts no command
