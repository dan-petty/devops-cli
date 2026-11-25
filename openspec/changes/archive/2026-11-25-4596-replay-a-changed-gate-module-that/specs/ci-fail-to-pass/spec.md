## ADDED Requirements

### Requirement: A changed module directly under tests/gate is replayed with its row
`devops ci fail-to-pass` SHALL list each added or changed `.py` module directly under `tests/gate/`, other than `__init__.py`, and replay it with the `devops ci` row whose command runs it. It SHALL run the module once in a worktree of the merge base and once in a worktree of the head, and its dry run SHALL list both runs. It MUST exit 1 and name the module when no row runs it.

#### Scenario: A changed gate module of a row
- **WHEN** `uv run devops ci fail-to-pass --base main` runs on a change that touches `tests/gate/ruff_config.py` and no other file
- **THEN** the command runs the module in a worktree of the merge base and in a worktree of the head, and the report names that module

#### Scenario: The dry run lists the module runs
- **WHEN** `uv run devops ci fail-to-pass --base main --dry-run` runs on a change that touches `tests/gate/startup_imports.py`
- **THEN** the plan holds one module run for the merge base and one for the head, and each names that module

#### Scenario: A module that no row runs
- **WHEN** `uv run devops ci fail-to-pass --base main` runs on a change that touches `tests/gate/runner.py` and no other file
- **THEN** the command exits 1 and the report names `tests/gate/runner.py` as a module that no `devops ci` row runs

### Requirement: One problem per line
The four gate modules that print their own problem lines SHALL write each problem as one physical line on standard error, and SHALL exit 1 when they write one. Each line SHALL carry a prefix: `ruff configuration: `, `construct gate: `, `startup imports: ` and `swallowed failures: `. A newline inside a problem MUST become a space.

#### Scenario: A start-up import problem with an embedded report
- **WHEN** `uv run devops ci --check --only startup-imports` runs the probes of `tests/gate/startup_imports.py` and a probe fails with a report that holds a newline
- **THEN** the standard error of the row holds one line for that problem and no embedded newline, and the row exits 1

#### Scenario: A swallowed-failures problem
- **WHEN** `uv run devops ci --check --only swallowed-failures` runs `tests/gate/swallowed_failures.py` and a file of the source tree is over its ceiling
- **THEN** the standard error of the row holds one line for each site of that file and no embedded newline, and the row exits 1

### Requirement: A base-only problem line proves the fix
`devops ci fail-to-pass` SHALL exit 0 when a line of the standard error of the base run of a changed module directly under `tests/gate/` appears on no line of the head run. Its report SHALL name the changed module and each such problem line.

#### Scenario: A ruff configuration problem fixed
- **WHEN** `uv run devops ci fail-to-pass --base main` runs on a change to `tests/gate/ruff_config.py`, and the base run writes the line `ruff configuration: linter.mccabe.max_complexity: 5, not 10` while the head run writes no line with that text
- **THEN** the command exits 0 and the report names `tests/gate/ruff_config.py` and that line

#### Scenario: A problem line that only the head run writes
- **WHEN** `uv run devops ci fail-to-pass --base main` runs on a change to `tests/gate/startup_imports.py`, and the head run writes a problem line that the base run does not
- **THEN** the command exits 1 and the report names that module and that line as one that only the head run writes

### Requirement: No base problem refuses the replay
`devops ci fail-to-pass` MUST exit 1 when a changed module directly under `tests/gate/` writes no problem line on the base run, and its report SHALL say that the base run of that module had no problem line. It MUST exit 1 when a run of the module exits with a status outside `CONST_FAIL_TO_PASS_GATE_ROW_EXIT_STATUSES`, and its report SHALL name the module, the tree and the exit status.

#### Scenario: A module that writes no problem on the base run
- **WHEN** `uv run devops ci fail-to-pass --base main` runs on a change that touches only `tests/gate/swallowed_failures.py`, and its base run writes no line on standard error
- **THEN** the command exits 1 and the report says that the base run of `tests/gate/swallowed_failures.py` had no problem line

#### Scenario: A module run that could not run
- **WHEN** `uv run devops ci fail-to-pass --base main` runs on a change to `tests/gate/construct_gate.py`, and the base run exits with a status other than 0 or 1
- **THEN** the command exits 1 and the report names that module, the merge base and the exit status

## MODIFIED Requirements

### Requirement: The check runs only for a fix that changes the code under src or a gate check
The fail-to-pass workflow SHALL start only for a pull request into `main` that changes a `.py` file under `src/` outside `src/devops_cli/ai/knowledge_base/`, or a path under `tests/gate/`, and its job SHALL run only for a title that `CONST_DEFECT_TITLE_PATTERN` reads as a fix and an author that is not `dan-petty-renovate[bot]`. Its comment MUST say that a changed gate module can write a problem line that fails on the base, and that a prompt, a pin or other data under `src/` is no code.

#### Scenario: A pull request that is not a fix
- **WHEN** the job condition of `.github/workflows/fail-to-pass.yml` is evaluated for the titles `feat(ci): add a check`, `docs(ci): describe the check`, `chore(main): release 1.0.0` and `fixup: squash a commit`
- **THEN** the job does not run for any of them

#### Scenario: A fix title
- **WHEN** the job condition is evaluated for `fix(ci): replay the changed tests`, `fix: replay the changed tests` and `FIX(ci): replay the changed tests`
- **THEN** the job runs for each of them

#### Scenario: A dependency bump of the Renovate App
- **WHEN** the job condition is read
- **THEN** it holds `github.event.pull_request.user.login != 'dan-petty-renovate[bot]'` and names no other author, so the fix pull requests of the Service App keep the check

#### Scenario: A change outside the code under src
- **WHEN** the path filter of the workflow is evaluated for `tests/ci/test_fail_to_pass.py`, `k8s/otel/values.yaml`, `Dockerfile`, `src/devops_cli/ai/knowledge_base/devops_cli/tasks/testing.md`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/review/rules/rules.lock` and the files of a release pull request
- **THEN** the workflow does not start for any of them, and it starts for `src/devops_cli/ci/fail_to_pass.py` and for `tests/gate/runner.py`, which `uv run devops ci fail-to-pass --base main` names as a module that no row runs

#### Scenario: A gate module pull request
- **WHEN** the path filter of the workflow is evaluated for `tests/gate/startup_imports.py`
- **THEN** the workflow starts, the comment of the workflow names `tests/gate/**` and no longer names `tests/gate/*_checks/**`, and `uv run devops ci --check --only actionlint,zizmor` validates the workflow

#### Scenario: The widened path filter validates
- **WHEN** `uv run devops ci --check --only actionlint,zizmor` validates `.github/workflows/fail-to-pass.yml`
- **THEN** the `paths` list holds `tests/gate/**` and no longer holds `tests/gate/*_checks/**`

#### Scenario: A gate check pull request
- **WHEN** the path filter of the workflow is evaluated for `tests/gate/k8s_checks/otel_collector.py`
- **THEN** the workflow starts, and the comment of the workflow names `tests/gate/*_checks/` and holds no sentence that only `src/` can make a test fail on base

### Requirement: A changed gate check is replayed with its row
`devops ci fail-to-pass` SHALL list each added or changed module directly under `tests/gate/<row>_checks/`, other than `__init__.py` and other than a module that only loses checks. For each row of these modules, it SHALL run `tests.gate.<row>` once on the base tree with the tests of the head, and once on the head tree. It SHALL run no other gate module.

#### Scenario: The k8s row
- **WHEN** `uv run devops ci fail-to-pass --base main` runs on a change to `tests/gate/k8s_checks/otel_collector.py`
- **THEN** the command runs `tests.gate.k8s` on the base tree and on the head tree, and no other gate module

#### Scenario: A test-only fix
- **WHEN** `uv run devops ci fail-to-pass --base main` runs on a change that touches only `tests/ci/test_fail_to_pass.py`
- **THEN** the command runs the pytest replay of that file, starts no gate row, and writes the same report as before the gate replay

#### Scenario: A module that only loses checks next to a changed module
- **WHEN** `tests/gate/k8s_checks/monitoring.py` only loses one check, and `uv run devops ci fail-to-pass --base main` runs on a change to `tests/gate/k8s_checks/otel_collector.py`
- **THEN** the command runs `tests.gate.k8s` on both trees, and the report names `tests/gate/k8s_checks/otel_collector.py` and not `tests/gate/k8s_checks/monitoring.py` as a changed gate check

### Requirement: A fix that changes no source code and no gate module needs no failing proof
`devops ci fail-to-pass` SHALL pass with no replay, and SHALL say that the fix changes no source code and no gate module, when the diff from the merge base holds no `.py` file under `src/` outside the knowledge base, no module of `tests/gate/*_checks/` and no `.py` module directly under `tests/gate/`.

#### Scenario: A fix of a prompt
- **WHEN** a fix changes only `src/devops_cli/ai/tasks/roadmap_stage_change.md` and a test that passes on base
- **THEN** the command exits 0, starts no pytest, and says that the fix changes no source code

#### Scenario: A fix of a rule lock
- **WHEN** a fix changes only `src/devops_cli/review/rules/rules.lock`
- **THEN** the command exits 0 and starts no pytest

#### Scenario: A fix of one gate module
- **WHEN** `uv run devops ci fail-to-pass --base main` runs on a change that touches only `tests/gate/ruff_config.py`
- **THEN** the command does not pass with no replay: it runs the module on the merge base and on the head tree, and exits 1 when the base run writes no problem line

## RENAMED Requirements

- FROM: `### Requirement: A fix that changes no source code needs no failing proof`
- TO: `### Requirement: A fix that changes no source code and no gate module needs no failing proof`
