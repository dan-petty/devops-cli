# ci-fail-to-pass Specification

## Purpose
When the fail-to-pass check runs on a pull request, what the replay reads, and what its report tells the author: only a fix that changes the code under `src/` or a gate check must show a changed test that fails on its base, or a case of a changed gate check that fails on its base and passes on its head.

## Requirements

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

### Requirement: The replay reads no title, label or body
`devops ci fail-to-pass` SHALL take no pull request title, label or body. It SHALL fail unless at least one changed test fails on base, or errors there at collection or setup, or a case of a changed gate check fails on base and passes on head.

#### Scenario: An escape line in the environment
- **WHEN** `PR_TITLE` is `feat(ci): add a check`, `PR_BODY` holds `Fail-to-pass: not applicable: the tests pass on base`, and every changed test passes on base
- **THEN** `devops ci fail-to-pass --base main` exits 1 and prints no `not applicable` line

#### Scenario: The removed options
- **WHEN** `devops ci fail-to-pass` gets `--title`, `--labels` or `--body`
- **THEN** it exits 2 as for an unknown option

### Requirement: A replay that cannot run names the next step

When the replay's pytest is interrupted, stops with an internal or usage error, passes the
process-runner limit, or writes no complete JUnit report, the check SHALL fail, and its report
SHALL tell the author to merge the change to the test harness or the dependencies first, in a pull
request that is not a fix.

#### Scenario: pytest stops with an internal error

- **WHEN** the replay's pytest exits with status 3 and writes no JUnit report
- **THEN** the command exits 1, and its report says that the replay could not run and to merge the change to the test harness or to the dependencies first, in a pull request that is not a fix

### Requirement: A host path guard failure refuses the replay
`devops ci fail-to-pass` SHALL treat a replay as not satisfied when a failure or an error of the replay carries the message `host path reached without a fake`, which the host path guard of the test harness writes, and its report SHALL name the tests that carry it and the two causes: a path that the harness does not allow, and a path that a test reads with no fake.

#### Scenario: A host path guard failure
- **WHEN** a changed test fails on base and another test of the replay fails with `Failed: host path reached without a fake: <checkout>/.git/worktrees/tree/HEAD`
- **THEN** the command exits 1, and its report says that the host path guard of the test harness stopped the replay, names the second test and names the two causes

#### Scenario: A host path guard error on teardown
- **WHEN** a test of the replay errors on teardown with `Failed: host path reached without a fake`
- **THEN** the command exits 1 and the report names that guard failure

### Requirement: A network, process or keyring edge failure keeps the replay valid
`devops ci fail-to-pass` SHALL NOT treat the message of the network, process or keyring guard of the test harness as a reason to refuse a replay, since a fix that stops code from reaching an edge proves itself by a changed test that fails on base at that edge.

#### Scenario: A changed test fails at a process edge
- **WHEN** a changed test fails on base with `Failed: process edge reached without a fake: gh api user`
- **THEN** the replay is satisfied

### Requirement: An unchanged test that still fails on the head refuses the replay
`devops ci fail-to-pass` SHALL treat a replay as not satisfied when an unchanged test fails or errors on base and does not pass on the head, or when it passes on the plain merge base. It SHALL NOT refuse the replay for an unchanged test that fails or errors on the plain merge base and passes on the head.

#### Scenario: An unchanged test fails
- **WHEN** a changed test file holds one changed test that fails on base and one unchanged test that fails on base and does not pass on the head
- **THEN** the command exits 1, and its report says that a test the fix does not change does not pass on the head and names the unchanged test

#### Scenario: An unchanged test errors
- **WHEN** a changed test file holds one changed test that errors on base and one unchanged test that errors on base, passes on the plain merge base, and passes on the head
- **THEN** the command exits 1, and its report says that a test the fix does not change does not pass on the head and names the unchanged test

#### Scenario: An unchanged test that the head repairs
- **WHEN** a changed test file holds one changed test that fails on base and one unchanged test that fails on base, fails on the plain merge base, and passes on the head
- **THEN** the command exits 0, and its report names the unchanged test as repaired on the head

#### Scenario: An unchanged test that passes on the plain merge base refuses the replay
- **WHEN** a changed test file holds one changed test that fails on base and one unchanged test that fails on base, passes on the plain merge base, and passes on the head
- **THEN** the command exits 1, and its report says that a test the fix does not change fails on base and names the unchanged test

#### Scenario: A comment changes no test
- **WHEN** the head of a test only adds a comment or a blank line to a test that fails on base
- **THEN** the test counts as unchanged

#### Scenario: A changed helper changes every test
- **WHEN** the head of a changed test file changes a helper of that file, and a test that calls the helper and that the fix leaves alone fails on base
- **THEN** the replay is satisfied

### Requirement: One new test that fails on base keeps the replay valid
`devops ci fail-to-pass` SHALL treat a test that the fix adds as changed, so a fix with one new test that fails on base is satisfied when no failure carries the message of the host path guard.

#### Scenario: The only test of the file is new
- **WHEN** a fix adds one test to a test file and the replay fails that test with an assertion
- **THEN** the replay is satisfied

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

### Requirement: A gate row that cannot run refuses the replay
`devops ci fail-to-pass` MUST exit 1 when a row run exits with a status other than 0 or 1, or prints no case summary. The report SHALL name the row, the tree, the exit status and the last lines of the output of the run.

#### Scenario: A row that cannot import
- **WHEN** the row run on the base tree exits 1 with a traceback and no `cases, N failed` summary line
- **THEN** the command exits 1, and the report names the row, the base tree, the exit status and the last lines of the output

### Requirement: The head run of a named head uses a worktree of that head
For `--head HEAD`, `devops ci fail-to-pass` SHALL run the head row and the head replay of the unchanged failures in the working tree, so an uncommitted change counts. For another head, it SHALL run both in one detached worktree of that head, and remove that worktree after the runs.

#### Scenario: A named head
- **WHEN** the command runs with `--head feature` for a fix that changes a gate check
- **THEN** it adds one detached worktree of `feature`, runs the head row there, and removes the worktree

#### Scenario: A named head with an unchanged failure
- **WHEN** the command runs with `--head feature` for a fix whose base replay holds an unchanged failure
- **THEN** it runs the head replay of those test files in the same worktree

#### Scenario: The default head
- **WHEN** the command runs with the default `--head HEAD` and the base replay holds an unchanged failure
- **THEN** it runs the head replay in the working tree and adds no worktree

### Requirement: The dry run lists the gate row runs
`devops ci fail-to-pass --dry-run` SHALL list the base and head runs of a gate row with the condition `a changed gate check exists`, and SHALL start no process.

#### Scenario: A dry run
- **WHEN** the dry run runs
- **THEN** the plan lists the two gate row runs with the condition `a changed gate check exists`, and the process fake records no call

### Requirement: Each gate row run imports the source of its tree
`devops ci fail-to-pass` SHALL start the gate row of each tree with the `src/` of that tree first on the import path. The base run SHALL import `devops_cli` from the `src/` of the base tree, and the head run from the `src/` of the head tree, also when the editable install of the interpreter names the `src/` of another checkout.

#### Scenario: A fix that adds a manifest and lists it in src
- **WHEN** a fix adds `k8s/b.yaml`, names it in a list of `src/`, and changes a check module of a gate row, and a check module that the fix does not change reads that list
- **THEN** the unchanged check module passes on the base tree, the changed case fails on base and passes on head, and the replay is satisfied

#### Scenario: The interpreter names the head source
- **WHEN** the interpreter that runs the command finds `devops_cli` in the `src/` of the head checkout
- **THEN** the gate row run on the base tree still imports `devops_cli` from the `src/` of the base tree

### Requirement: The report names a repaired test
`devops ci fail-to-pass` SHALL name in its report each test that the fix does not change, that fails or errors on the plain merge base and that passes on the head, and each unchanged test file whose file-level collection error on the plain merge base is followed by at least one head case and only passing head cases for that file, as repaired on the head.

#### Scenario: A repaired test in the report
- **WHEN** an unchanged test fails on base, fails on the plain merge base, and passes on the head
- **THEN** the report holds a line that names the test and says that the head repairs it

#### Scenario: All head cases of a file with a collection error pass
- **WHEN** the base and plain merge base reports hold an error case with the module-path id of an unchanged test file and the head report holds passing cases for each test of that file
- **THEN** `_repaired_and_refused` counts the file as repaired and does not refuse it

### Requirement: A head replay that cannot run refuses the replay

`devops ci fail-to-pass` SHALL treat a replay as not satisfied when the head replay of the test
files that hold an unchanged failure is interrupted, stops with an internal or usage error, passes
the process-runner limit, or writes no complete JUnit report. Its report SHALL name the head run
and pytest's exit status, or the limit when pytest passed it.

#### Scenario: A head replay that writes no complete report

- **WHEN** the head replay of the test files that hold an unchanged failure writes no complete JUnit report
- **THEN** the command exits 1, and its report says that the replay could not run on the head and names pytest's exit status

#### Scenario: A head replay that passes the process-runner limit

- **WHEN** the head replay stops after `DEFAULT_SUBPROCESS_TIMEOUT_SECONDS`
- **THEN** the command exits 1, and its report names the limit and the test files and prints no pytest exit status

### Requirement: The dry run lists the head replay
`devops ci fail-to-pass --dry-run` SHALL list the head replay of the test files that hold an unchanged failure with the condition `a test that failed or errored on base is unchanged`, and SHALL start no process.

#### Scenario: A dry run of the head replay
- **WHEN** `devops ci fail-to-pass --dry-run` runs
- **THEN** the plan lists the head pytest run with the condition `a test that failed or errored on base is unchanged`, and the process fake records no call

### Requirement: A replay that passes the process-runner limit names the limit

When a replay stops after `DEFAULT_SUBPROCESS_TIMEOUT_SECONDS`, the report SHALL name the limit and
each test file of the replay, and SHALL NOT print a pytest exit status that pytest did not return.
The base, plain-base, head and gate-row replays SHALL use this report.

#### Scenario: The base replay passes the limit

- **WHEN** the base replay stops after `DEFAULT_SUBPROCESS_TIMEOUT_SECONDS`
- **THEN** the command exits 1, the report names the limit and the test files, and it prints no traceback or pytest exit status

#### Scenario: A gate row passes the limit

- **WHEN** a gate-row replay stops after `DEFAULT_SUBPROCESS_TIMEOUT_SECONDS`
- **THEN** the report names the row, the tree and the limit, and prints no pytest exit status

### Requirement: A changed test that errors on base proves the fix
`devops ci fail-to-pass` SHALL count a changed test that errors on base at collection or setup as a proof of the fix, as it counts a changed test that fails in the call phase. An error at teardown SHALL NOT prove the fix. A collection error names a whole test file: it SHALL count as changed when the syntax tree of the file differs from the merge base or the file is new. The report SHALL name each changed test that proves the fix.

#### Scenario: The only changed test file fails to collect on base
- **WHEN** the fix changes `tests/test_sample.py`, and the replay reports only a collection error of `tests.test_sample`
- **THEN** the command exits 0, and its report names `tests.test_sample` as errored on base and as the proof of the fix

#### Scenario: A changed test errors on setup
- **WHEN** a changed test errors on base with `failed on setup with "AttributeError: module has no attribute 'new_field'"`
- **THEN** the replay is satisfied

#### Scenario: A changed test errors only at teardown
- **WHEN** the only changed test passes in the call phase on base and errors with `failed on teardown with "AttributeError: fixture has no attribute 'close'"`
- **THEN** the replay is not satisfied, and its report says that a fix needs a changed test that fails on base, or that errors there at collection or setup

#### Scenario: A comment does not change an errored file
- **WHEN** the head of a test file adds only a comment, and the file fails to collect on base
- **THEN** the command exits 1, and its report says that a test the fix does not change does not pass on the head and names the file

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
- **WHEN** `tests/gate/k8s_checks/gateway.py` loses `check_old_rule` and a helper with a decorator other than a pytest mark or a `functools` decorator, a call in the arguments of a decorator, a call in a default value, a class with a base, or an import of a module of the project that the head does not import
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

### Requirement: The replay keeps the addopts of the tree
The pytest run of the replay SHALL keep the `addopts` of the tree that it runs in, and SHALL start no xdist worker. A test that reads `addopts` SHALL pass in the replay when it passes in a normal run.

#### Scenario: A test reads addopts in the replay
- **WHEN** the replay runs a test that reads `addopts` and the number of xdist workers, in a project whose `addopts` give `-n 2`
- **THEN** the test reads the `addopts` of the project and 0 workers, and the JUnit report of the replay gives it as passed

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

### Requirement: File-level collection error without passing head cases is refused
`_repaired_and_refused` SHALL refuse a file-level collection error when any head case of that file does not pass or when the head report holds no case for that file.

#### Scenario: One head case of the file fails
- **WHEN** the plain merge base report holds an error case with the module-path id of a test file and the head report holds a failing case for one test of that file
- **THEN** `_repaired_and_refused` refuses the file

#### Scenario: The head report has no case for the file
- **WHEN** the plain merge base report holds an error case with the module-path id of a test file and the head report holds no case for that file
- **THEN** `_repaired_and_refused` refuses the file

### Requirement: Documentation states the error rule
The `Fail-to-Pass Evidence` section of `CONTRIBUTING.md` SHALL state that an unchanged test is repaired when it fails or errors on the plain merge base and that a file-level collection error is repaired when every head case of that file passes.

#### Scenario: The documentation check passes
- **WHEN** `uv run devops ci --check --only docs` runs on the branch
- **THEN** the command exits 0 and the docs row reports no stale document

### Requirement: Phase reader follows real pytest
The fail-to-pass test suite SHALL include a test that runs real pytest on a module with a collection error and on tests with setup and teardown errors and asserts the phase (`collection`, `setup`, `teardown`) that `TestCaseOutcome.error_phase` reads from the JUnit XML.

#### Scenario: Real pytest collection and setup errors
- **WHEN** the test runs pytest in a subprocess on a temporary directory that holds a module whose import raises and a test whose fixture raises, then parses the JUnit XML
- **THEN** `TestCaseOutcome.error_phase` reads `'collection'` for the module case and `'setup'` for the fixture setup case
