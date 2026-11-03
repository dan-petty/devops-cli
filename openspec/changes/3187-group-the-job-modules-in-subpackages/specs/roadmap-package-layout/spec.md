## Purpose
The layout of the roadmap package: one subpackage for each roadmap job and one for the stores, so a reader sees which modules belong to one job, and every caller names the module path that it imports.

## ADDED Requirements

### Requirement: Each roadmap job has its own subpackage
The roadmap package SHALL hold one subpackage for each job, `intake`, `refine`, `stage` and `implement`, and SHALL hold no module at its top level whose name starts with a job name.

#### Scenario: No top-level module carries a job prefix
- **WHEN** A test lists the module names at the top level of `src/devops_cli/roadmap/`.
- **THEN** No listed name starts with `intake`, `refine`, `stage` or `implement`, and each of the four job subpackages holds at least one module.

### Requirement: The store modules sit under stores
The roadmap package SHALL hold the store interface, the GitHub adapter and the in-memory adapter in `src/devops_cli/roadmap/stores/`.

#### Scenario: Every store module is under stores
- **WHEN** A test lists the module names of `src/devops_cli/roadmap/stores/` and of the top level of `src/devops_cli/roadmap/`.
- **THEN** The `stores` folder holds `store.py`, `github_store.py` and `memory_store.py`, and the top level holds no module with one of those names.

### Requirement: Every caller imports a roadmap module by its path
Every import of a roadmap module under `src/` and `tests/` SHALL name the module path in the package.

#### Scenario: No old roadmap module path remains
- **WHEN** A test searches `src/` and `tests/` for an import that names `store`, `github_store`, `memory_store`, `intake`, `refine`, `stage` or `implement_step` as a direct child of `devops_cli.roadmap`.
- **THEN** The search finds no match.

### Requirement: The roadmap package module exports no name
The module `src/devops_cli/roadmap/__init__.py` SHALL hold its docstring and SHALL NOT import or re-export a moved module.

#### Scenario: The package module holds only a docstring
- **WHEN** A test parses `src/devops_cli/roadmap/__init__.py`.
- **THEN** The module body holds one docstring and no import, assignment, class or function definition.
