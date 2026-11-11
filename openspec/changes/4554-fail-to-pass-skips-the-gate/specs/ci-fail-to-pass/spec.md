## RENAMED Requirements

- FROM: `### Requirement: The check runs only for a fix that changes the code under src`
- TO: `### Requirement: The check runs only for a fix that changes the code under src or a gate check`

## MODIFIED Requirements

### Requirement: The check runs only for a fix that changes the code under src or a gate check
The fail-to-pass workflow SHALL start only for a pull request into `main` that changes a path under `src/` outside `src/devops_cli/ai/knowledge_base/`, or a path under `tests/gate/*_checks/`, and its job SHALL run only for a title that `CONST_DEFECT_TITLE_PATTERN` reads as a fix. Its comment MUST say that a changed gate check can fail on the base.

#### Scenario: A pull request that is not a fix
- **WHEN** the job condition of `.github/workflows/fail-to-pass.yml` is evaluated for the titles `feat(ci): add a check`, `docs(ci): describe the check`, `chore(main): release 1.0.0` and `fixup: squash a commit`
- **THEN** the job does not run for any of them

#### Scenario: A fix title
- **WHEN** the job condition is evaluated for `fix(ci): replay the changed tests`, `fix: replay the changed tests` and `FIX(ci): replay the changed tests`
- **THEN** the job runs for each of them

#### Scenario: A change outside the code under src
- **WHEN** the path filter of the workflow is evaluated for `tests/test_fail_to_pass.py`, `tests/gate/runner.py`, `k8s/otel/values.yaml`, `Dockerfile`, `src/devops_cli/ai/knowledge_base/devops_cli/tasks/testing.md` and the files of a release pull request
- **THEN** the workflow does not start for any of them, and it starts for `src/devops_cli/ci/fail_to_pass.py`

#### Scenario: A gate check pull request
- **WHEN** the path filter of the workflow is evaluated for `tests/gate/k8s_checks/otel_collector.py`
- **THEN** the workflow starts, and the comment of the workflow names `tests/gate/*_checks/` and holds no sentence that only `src/` can make a test fail on base

### Requirement: The replay reads no title, label or body
`devops ci fail-to-pass` SHALL take no pull request title, label or body. It SHALL fail unless at least one changed test fails in the call phase on base, or a case of a changed gate check fails on base and passes on head.

#### Scenario: An escape line in the environment
- **WHEN** `PR_TITLE` is `feat(ci): add a check`, `PR_BODY` holds `Fail-to-pass: not applicable: the tests pass on base`, and every changed test passes on base
- **THEN** `devops ci fail-to-pass --base main` exits 1 and prints no `not applicable` line

#### Scenario: The removed options
- **WHEN** `devops ci fail-to-pass` gets `--title`, `--labels` or `--body`
- **THEN** it exits 2 as for an unknown option

## ADDED Requirements

### Requirement: A changed gate check is replayed with its row
`devops ci fail-to-pass` SHALL list each added or changed module directly under `tests/gate/<row>_checks/`, other than `__init__.py`. For each row of these modules, it SHALL run `tests.gate.<row>` once on the base tree with the tests of the head, and once on the head tree. It SHALL run no other gate module.

#### Scenario: The k8s row
- **WHEN** the fix changes `tests/gate/k8s_checks/otel_collector.py`
- **THEN** the command runs `tests.gate.k8s` on the base tree and on the head tree, and no other gate module

#### Scenario: A test-only fix
- **WHEN** the fix changes only `tests/test_mod.py`
- **THEN** the command runs the pytest replay of that file, starts no gate row, and writes the same report as before the gate replay

### Requirement: A gate case that fails on base and passes on head proves the fix
`devops ci fail-to-pass` SHALL count a case of a changed check module as a proof when the base run fails it, the head run does not fail it, and both runs count the same cases. The report SHALL name each changed check module and each such case.

#### Scenario: A k8s gate check fails on base
- **WHEN** the fix changes `tests/gate/k8s_checks/otel_collector.py`, and the `k8s` row fails one case of that module on the base tree and passes it on the head tree
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
- **WHEN** the `k8s` row fails `other_module.check_other` on the base tree, and the fix changes only `tests/gate/k8s_checks/otel_collector.py`
- **THEN** the command exits 1, and the report names `other_module.check_other` as a failure of a module that the fix does not change

### Requirement: A gate row that cannot run refuses the replay
`devops ci fail-to-pass` MUST exit 1 when a row run exits with a status other than 0 or 1, or prints no case summary. The report SHALL name the row, the tree, the exit status and the last lines of the output of the run.

#### Scenario: A row that cannot import
- **WHEN** the row run on the base tree exits 1 with a traceback and no `cases, N failed` summary line
- **THEN** the command exits 1, and the report names the row, the base tree, the exit status and the last lines of the output

### Requirement: The head run of a named head uses a worktree of that head
For `--head HEAD`, `devops ci fail-to-pass` SHALL run the head row in the working tree, so a change that is not committed counts. For another head, it SHALL run the head row in a detached worktree of that head, and remove that worktree after the run.

#### Scenario: A named head
- **WHEN** the command runs with `--head feature` for a fix that changes a gate check
- **THEN** it adds a detached worktree of `feature`, runs the head row there, and removes the worktree

### Requirement: The dry run lists the gate row runs
`devops ci fail-to-pass --dry-run` SHALL list the base and head runs of a gate row with the condition `a changed gate check exists`, and SHALL start no process.

#### Scenario: A dry run
- **WHEN** the dry run runs
- **THEN** the plan lists the two gate row runs with the condition `a changed gate check exists`, and the process fake records no call
