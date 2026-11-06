## Purpose
The layout of the roadmap package: one subpackage for each roadmap job and one for the stores, so a reader sees which modules belong to one job, and every caller names the module path that it imports.

## ADDED Requirements

### Requirement: Each roadmap job has its own subpackage
The roadmap package SHALL hold one subpackage for each job, `intake`, `refine`, `stage` and `implement`, and SHALL hold no module at its top level whose name starts with a job name.

#### Scenario: No top-level module carries a job prefix
- **WHEN** A test lists the module names at the top level of `src/devops_cli/roadmap/` and of the four job subpackages.
- **THEN** No top-level name starts with `intake`, `refine`, `stage` or `implement`, and each of the four job subpackages holds at least one module.

### Requirement: The store modules sit under stores
The roadmap package SHALL hold the store interface and the GitHub adapter in `src/devops_cli/roadmap/stores/`.

#### Scenario: Every store module is under stores
- **WHEN** A test lists the module names of `src/devops_cli/roadmap/stores/` and of the top level of `src/devops_cli/roadmap/`.
- **THEN** The `stores` folder holds `store.py` and `github_store.py`, and the top level holds no module with one of those names.

### Requirement: Every caller imports a roadmap module by its path
Every import of a roadmap module under `src/` and `tests/` SHALL name the module path in the package.

#### Scenario: No old roadmap module path remains
- **WHEN** A test parses each import of `devops_cli.roadmap` in `src/` and `tests/`.
- **THEN** Each imported module file or package folder exists, and each name imported from a package that holds only a docstring is a submodule.

### Requirement: The roadmap package module exports no name
The module `src/devops_cli/roadmap/__init__.py` SHALL hold its docstring and SHALL NOT import or re-export a moved module.

#### Scenario: The package module holds only a docstring
- **WHEN** A test parses `src/devops_cli/roadmap/__init__.py`.
- **THEN** The module body holds one docstring and no import, assignment, class or function definition.

### Requirement: History follows each move
Each module of the change SHALL move with `git mv`, so that `git log --follow` reports the commits that touched the module before the move.

#### Scenario: The log of a moved module reaches its old path
- **WHEN** A test runs `git log --follow --oneline` on a moved module path.
- **THEN** The log holds the commit that created the module at its old path.

### Requirement: The roadmap test tree mirrors the subpackages
The tests of a moved module SHALL sit in the directory under `tests/roadmap/` that mirrors the subpackage of the module, and each snapshot file SHALL sit in the `__snapshots__` directory beside its test module.

#### Scenario: No job test module stays flat
- **WHEN** A test lists the test modules directly under `tests/roadmap/` and under `tests/roadmap/intake/`, `tests/roadmap/refine/`, `tests/roadmap/stage/`, `tests/roadmap/implement/` and `tests/roadmap/stores/`.
- **THEN** No test module with a job prefix in its name sits directly under `tests/roadmap/`, and each moved test module has its snapshot file beside it.

### Requirement: Runtime behavior does not change
The change SHALL move modules and rewrite paths, and SHALL NOT change what a roadmap command does.

#### Scenario: The full suite passes with no changed assertion
- **WHEN** The full test suite runs on the changed tree.
- **THEN** Every test passes, and no test assertion differs from the one on the base tree.
