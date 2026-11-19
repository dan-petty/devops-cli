## ADDED Requirements

### Requirement: A gate check module that only loses checks needs no proof
`devops ci fail-to-pass` SHALL count a changed gate check module as one that only loses checks when its head keeps the top-level statements of its base in order, by syntax tree, and leaves out at least one `def check_*` and only imports, assignments, functions and classes whose names the head does not use. When the fix changes no source code, and each gate check module that it changes only loses checks or is deleted, the command SHALL pass with no replay and name each deleted check.

#### Scenario: A fix that only deletes a check
- **WHEN** a fix changes no `.py` file under `src/`, and `tests/gate/k8s_checks/gateway.py` loses `check_old_rule`, a constant that only `check_old_rule` read, and the text of a comment
- **THEN** the command exits 0, starts no pytest and no gate row, and the report names `gateway.check_old_rule`

#### Scenario: A deleted check and a changed check
- **WHEN** a fix changes no `.py` file under `src/`, and `tests/gate/k8s_checks/gateway.py` loses `check_old_rule` and changes the body of another check
- **THEN** the command runs `tests.gate.k8s` on the base tree and on the head tree, and the report names no deleted check

#### Scenario: A deleted check and an added check
- **WHEN** a fix changes no `.py` file under `src/`, and `tests/gate/k8s_checks/gateway.py` loses `check_old_rule` and gains `check_new_rule`
- **THEN** the command runs `tests.gate.k8s` on the base tree and on the head tree

#### Scenario: A deleted check and a changed helper
- **WHEN** `tests/gate/k8s_checks/gateway.py` loses `check_old_rule` and changes a helper that a kept check calls
- **THEN** the module does not only lose checks, and the command runs `tests.gate.k8s` on both trees

#### Scenario: A moved statement
- **WHEN** `tests/gate/k8s_checks/gateway.py` loses `check_old_rule`, and two kept top-level statements change places
- **THEN** the module does not only lose checks

#### Scenario: A left-out statement that the head still uses
- **WHEN** `tests/gate/k8s_checks/gateway.py` loses `check_old_rule` and a second assignment of a name that a kept check reads
- **THEN** the module does not only lose checks

#### Scenario: A new or unreadable module
- **WHEN** the fix adds `tests/gate/k8s_checks/new.py`, or a side of a changed check module does not parse
- **THEN** the module does not only lose checks, and the command runs its gate row as before

#### Scenario: A deleted check in a fix of source code
- **WHEN** a fix changes a `.py` file under `src/` and no test file, and its only other change deletes `check_old_rule` of `tests/gate/k8s_checks/gateway.py`
- **THEN** the command starts no gate row, exits 1, and says that the fix changes no test and no gate check that can fail on its base

### Requirement: A left-out statement runs no code at import
`devops ci fail-to-pass` SHALL count a left-out statement as one that runs code at import when it holds a call outside a function body, a decorator other than a pytest mark or a `functools` decorator, a class base or keyword, or an import of a module of the project that the head does not import. A module that leaves out such a statement SHALL NOT count as one that only loses checks.

#### Scenario: A left-out cached helper
- **WHEN** `tests/gate/k8s_checks/gateway.py` loses `check_old_rule`, a helper with the decorator `functools.cache` that only `check_old_rule` calls, and `import functools`
- **THEN** the report names `gateway.check_old_rule`

#### Scenario: A left-out top-level call
- **WHEN** `tests/gate/k8s_checks/gateway.py` loses `check_old_rule` and a top-level call that sets state, also when an assignment holds the call
- **THEN** the module does not only lose checks

#### Scenario: A left-out statement that runs code at import
- **WHEN** `tests/gate/k8s_checks/gateway.py` loses `check_old_rule` and a helper with a decorator other than a pytest mark or a `functools` decorator, a call in a default value, a class with a base, or an import of a module of the project that the head does not import
- **THEN** the module does not only lose checks

### Requirement: A deleted gate check module names its checks
`devops ci fail-to-pass` SHALL keep a deleted gate check module out of the replay, and SHALL name each top-level `def check_*` of the module at the merge base as a deleted check.

#### Scenario: A deleted check module
- **WHEN** a fix changes no `.py` file under `src/`, deletes `tests/gate/k8s_checks/argo.py`, and `tests/gate/k8s_checks/gateway.py` only loses `check_old_rule`
- **THEN** the command passes, starts no gate row, and the report names each check of `argo.py` at the merge base and `gateway.check_old_rule`, in the order of the paths

### Requirement: The dry run lists the reads of a changed gate check module
`devops ci fail-to-pass --dry-run` SHALL list the `git ls-tree` and `git cat-file` reads of each changed or deleted module of `tests/gate/*_checks/` at the merge base, with the condition `a module of tests/gate/*_checks/ changes or is deleted`, and of each changed module at a named head, with the condition `a module of tests/gate/*_checks/ changes`. It SHALL start no process.

#### Scenario: A dry run with a named head
- **WHEN** `devops ci fail-to-pass --base main --head feature --dry-run` runs
- **THEN** the plan lists a read of the gate check module at `<merge-base>`, repeated for each changed or deleted module of `tests/gate/*_checks/`, and at `feature`, repeated for each changed module, and no process starts

## MODIFIED Requirements

### Requirement: A changed gate check is replayed with its row
`devops ci fail-to-pass` SHALL list each added or changed module directly under `tests/gate/<row>_checks/`, other than `__init__.py` and other than a module that only loses checks. For each row of these modules, it SHALL run `tests.gate.<row>` once on the base tree with the tests of the head, and once on the head tree. It SHALL run no other gate module.

#### Scenario: The k8s row
- **WHEN** the fix changes `tests/gate/k8s_checks/otel_collector.py`
- **THEN** the command runs `tests.gate.k8s` on the base tree and on the head tree, and no other gate module

#### Scenario: A test-only fix
- **WHEN** the fix changes only `tests/test_mod.py`
- **THEN** the command runs the pytest replay of that file, starts no gate row, and writes the same report as before the gate replay

#### Scenario: A module that only loses checks next to a changed module
- **WHEN** `tests/gate/k8s_checks/gateway.py` only loses `check_old_rule`, and the fix changes a check of `tests/gate/k8s_checks/otel_collector.py`
- **THEN** the command runs `tests.gate.k8s` on both trees, and the report names `tests/gate/k8s_checks/otel_collector.py` and not `tests/gate/k8s_checks/gateway.py` as a changed gate check
