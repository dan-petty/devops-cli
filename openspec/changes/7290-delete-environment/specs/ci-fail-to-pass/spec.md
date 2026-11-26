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
- **WHEN** the path filter of the workflow is evaluated for `tests/ci/test_fail_to_pass.py`, `k8s/devops/kustomization.yaml`, `Dockerfile`, `src/devops_cli/ai/knowledge_base/devops_cli/tasks/testing.md`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/review/rules/rules.lock` and the files of a release pull request
- **THEN** the workflow does not start for any of them, and it starts for `src/devops_cli/ci/fail_to_pass.py` and for `tests/gate/runner.py`, which `uv run devops ci fail-to-pass --base main` names as a module that no row runs

#### Scenario: A gate module pull request
- **WHEN** the path filter of the workflow is evaluated for `tests/gate/startup_imports.py`
- **THEN** the workflow starts, the comment of the workflow names `tests/gate/**` and no longer names `tests/gate/*_checks/**`, and `uv run devops ci --check --only actionlint,zizmor` validates the workflow

#### Scenario: The widened path filter validates
- **WHEN** `uv run devops ci --check --only actionlint,zizmor` validates `.github/workflows/fail-to-pass.yml`
- **THEN** the `paths` list holds `tests/gate/**` and no longer holds `tests/gate/*_checks/**`

#### Scenario: A gate check pull request
- **WHEN** the path filter of the workflow is evaluated for `tests/gate/k8s_checks/network_policies.py`
- **THEN** the workflow starts, and the comment of the workflow names `tests/gate/*_checks/` and holds no sentence that only `src/` can make a test fail on base

### Requirement: A changed gate check is replayed with its row
`devops ci fail-to-pass` SHALL list each added or changed module directly under `tests/gate/<row>_checks/`, other than `__init__.py` and other than a module that only loses checks. For each row of these modules, it SHALL run `tests.gate.<row>` once on the base tree with the tests of the head, and once on the head tree. It SHALL run no other gate module.

#### Scenario: The k8s row
- **WHEN** `uv run devops ci fail-to-pass --base main` runs on a change to `tests/gate/k8s_checks/network_policies.py`
- **THEN** the command runs `tests.gate.k8s` on the base tree and on the head tree, and no other gate module

#### Scenario: A test-only fix
- **WHEN** `uv run devops ci fail-to-pass --base main` runs on a change that touches only `tests/ci/test_fail_to_pass.py`
- **THEN** the command runs the pytest replay of that file, starts no gate row, and writes the same report as before the gate replay

#### Scenario: A module that only loses checks next to a changed module
- **WHEN** `tests/gate/k8s_checks/deploy_stack.py` only loses one check, and `uv run devops ci fail-to-pass --base main` runs on a change to `tests/gate/k8s_checks/network_policies.py`
- **THEN** the command runs `tests.gate.k8s` on both trees, and the report names `tests/gate/k8s_checks/network_policies.py` and not `tests/gate/k8s_checks/deploy_stack.py` as a changed gate check

### Requirement: A gate case that fails on base and passes on head proves the fix
`devops ci fail-to-pass` SHALL count a case of a changed check module as a proof when the base run fails it, the head run does not fail it, and both runs count the same cases. The report SHALL name each changed check module and each such case.

#### Scenario: A k8s gate check fails on base
- **WHEN** the fix changes `tests/gate/k8s_checks/network_policies.py`, and the `k8s` row fails one case of that module on the base tree and passes it on the head tree
- **THEN** the command exits 0, and the report names the case as failed on base and passed on head, names the module, and holds no `no changed test files` text

#### Scenario: A gate check passes on both trees
- **WHEN** the changed gate check passes on the base tree and on the head tree, and the fix changes no test file
- **THEN** the command exits 1, and the report says that no case of a changed gate check failed on base and passed on head

#### Scenario: The case count changes
- **WHEN** the base run counts 107 cases and the head run counts 106 cases
- **THEN** the command exits 1, and the report names the two counts

### Requirement: A base failure of an unchanged check module refuses the replay
`devops ci fail-to-pass` MUST exit 1 when the base run of a row fails a case of a check module that the fix does not change. The report SHALL name that case.

#### Scenario: An unrelated gate failure
- **WHEN** the `k8s` row fails `other_module.check_other` on the base tree, and the fix changes only `tests/gate/k8s_checks/network_policies.py`
- **THEN** the command exits 1, and the report names `other_module.check_other` as a failure of a module that the fix does not change
