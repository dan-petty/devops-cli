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
The `startup-imports` row SHALL start each argv in a fresh interpreter under `-X importtime`, SHALL keep the four module limits, and SHALL fail when a run imports a heavy package. It SHALL name the ten slowest imports of a failed run, and it SHALL report the child CPU time of each probe on its own line. It SHALL fail when the root help leaves `pydantic` loaded.

#### Scenario: The control
- **WHEN** the root help runs after an import of a heavy package
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

### Requirement: The domain row refuses a commit that names a configured domain
The table of `devops ci` SHALL hold a row `domain` that runs the `main` of `tests/gate/configured_domain.py`. The row SHALL read `k8s.domain` and `cloudflare.domain` from the config at run time, and each added line and path of each commit from `origin/main` to `HEAD`. It SHALL fail on a line or path that holds a configured domain, in any case, with no letter, digit or hyphen next to it.

#### Scenario: A commit names a configured domain
- **WHEN** `k8s.domain` is `example.net`, and a commit of the branch adds the line `host: api.example.net` as line 2 of `k8s/app.yaml`
- **THEN** the check gives the finding `k8s/app.yaml:2 in commit <sha> names the value of k8s.domain`

#### Scenario: A commit names only example.com
- **WHEN** `k8s.domain` is `example.net`, and the commits of the branch add `example.com`, `notexample.net` and `example.network`, and remove a line that names `api.example.net`
- **THEN** the check gives no finding

#### Scenario: The config spells the domain with a final dot
- **WHEN** `k8s.domain` is `example.net.` with a final dot, and a commit of the branch adds the line `host: api.example.net`
- **THEN** the check gives a finding for the line, because the row reads the domain in its ASCII form with no blank space and no final dot, and finds a Unicode label in its ASCII form and as Unicode

#### Scenario: A domain is configured
- **WHEN** the config sets `k8s.domain` to `example.net`, and `devops ci --only domain` runs
- **THEN** the row starts `uv run python -c` with the `main` of `tests.gate.configured_domain`

### Requirement: The domain row never prints the value of a domain
Each finding of the `domain` row SHALL name the path, the line, the commit and the settings key, and no output of the row SHALL hold the value of a domain. A path that names a domain SHALL be named by its commit only.

#### Scenario: The finding of a line holds no value
- **WHEN** `k8s.domain` is `example.net`, and a commit adds the line `host: api.example.net`
- **THEN** the output of the check does not hold `example.net`

#### Scenario: A path names a configured domain
- **WHEN** `cloudflare.domain` is `example.net`, and a commit adds the file `k8s/grafana.example.net.yaml`
- **THEN** the check gives `a path in commit <sha> names the value of cloudflare.domain`, with no path

### Requirement: The domain row is skipped where no domain is configured
When the config sets neither `k8s.domain` nor `cloudflare.domain`, the `domain` row SHALL start no command, SHALL pass, and SHALL show `skipped: <cause>`.

#### Scenario: No domain is configured
- **WHEN** the config sets neither `k8s.domain` nor `cloudflare.domain`, and `devops ci --only domain` runs
- **THEN** the row starts no command, the gate exits 0, and the output shows `[domain] skipped: no k8s.domain or cloudflare.domain is configured, so the row read no commit`

### Requirement: The pre-push hook runs the domain row
The pre-push hook `devops-ci-pre-push` SHALL run the rows `lint`, `format` and `domain` of `devops ci` in check-only mode.

#### Scenario: The hooks of a push
- **WHEN** the hooks of the `pre-push` stage of `.pre-commit-config.yaml` are read
- **THEN** the hook after `branch-current` runs `devops ci --check` with the rows `lint`, `format` and `domain`

### Requirement: The roadmap-eval-commits row checks the base commit of each golden case
The table of `devops ci` SHALL hold a row `roadmap-eval-commits` that runs the check module of the row from `tests/gate/`. The row SHALL read the golden stage eval cases, the golden implement eval cases and the git history of the repository, and it SHALL pass when each base commit that is not `NO_COMMIT` is a full hash that names a commit of the repository.

#### Scenario: The row reads the cases and the history
- **WHEN** `devops ci` runs the `roadmap-eval-commits` row
- **THEN** the row reads both golden sets and the git history of the repository and prints the count of cases that it read

#### Scenario: The golden set passes the row
- **WHEN** each stage or implement case whose base commit is not `NO_COMMIT` names a full hash of a commit of the repository, and each `NO_COMMIT` stage case has a note that says it reads no commit
- **THEN** the row passes and prints the count of stage and implement cases that it read

### Requirement: The roadmap-eval-commits row fails on a base commit that it cannot resolve
The row SHALL fail and SHALL name each stage or implement case whose base commit is not a full hash of a commit of the repository, and each stage case whose base commit is `NO_COMMIT` and whose notes do not say that it reads no commit.

#### Scenario: Base commit is no commit
- **WHEN** a stage or implement case names a 40-character hash that `git cat-file -e` cannot resolve as a commit
- **THEN** the row fails and its message names the case and the hash

#### Scenario: A case with no commit lacks the note
- **WHEN** a stage case has base commit `NO_COMMIT` and no note that says it reads no commit
- **THEN** the row fails and its message names the case

### Requirement: The roadmap-eval-commits row fails on a shallow clone
The row SHALL fail when the repository is a shallow clone, with a message that says the clone lacks the history that the golden cases name. The `static` job of `.github/workflows/ci.yml`, which runs the row, SHALL check out the full history with `fetch-depth: 0`.

#### Scenario: Shallow repository
- **WHEN** `git rev-parse --is-shallow-repository` prints `true`
- **THEN** the row fails and the message says that the shallow clone lacks the history that the golden cases need

#### Scenario: The Static Analysis job gives the row the full history
- **WHEN** a test reads the `Check out repository` step of the `static` job in `.github/workflows/ci.yml`
- **THEN** the step sets `fetch-depth: 0`

### Requirement: A shard test row has its own bound
The `test` row of a shard run SHALL stop at `DEFAULT_CI_TEST_SHARD_TIMEOUT_SECONDS` (900 s), and the unsharded row SHALL keep the default bound. The coverage-index build SHALL stop at `DEFAULT_CI_COVERAGE_INDEX_TIMEOUT_SECONDS` (3600 s).

#### Scenario: A shard test row
- **WHEN** the test row runs with `--shard 2 --shards 4`
- **THEN** its `timeout_seconds` is 900 s and its timeout line names the row

#### Scenario: The unsharded test row
- **WHEN** the test row runs with no shard
- **THEN** its `timeout_seconds` is None and the run takes the default bound

#### Scenario: The index build
- **WHEN** `devops ci coverage --build-index` starts the suite
- **THEN** the run takes `DEFAULT_CI_COVERAGE_INDEX_TIMEOUT_SECONDS` of 3600 s

### Requirement: Each row of the check registry is a subcommand
Each row of `get_check_specs()` SHALL be a subcommand of `devops ci` named after the row, and a row with no hand-written command SHALL get a generated command that runs the same path as `devops ci --only <row>`: the same gate slot, the same telemetry and the same request plan of a narrowed run. The list of commands SHALL come from a static tuple of row names, and the module SHALL NOT call `get_check_specs()` while it imports.

#### Scenario: A row with no hand-written command
- **WHEN** The test runs the row constructs and the row test-tree, each with `--dry-run`.
- **THEN** Each run exits 0, and its request plan holds one request for each command of that row's check spec and no request of another row.

#### Scenario: A row with a hand-written command
- **WHEN** The test runs the lint row with `--dry-run`.
- **THEN** The run exits 0 and plans the fix command of the lint row, which is its hand-written command.

### Requirement: The static row tuple matches the registry
The static tuple of row names in `src/devops_cli/commands/ci.py` SHALL hold the same names, in the same order, as `get_check_specs()`, so that a row that is added, renamed or removed fails the test that compares the two lists.

#### Scenario: A row is added, renamed or removed
- **WHEN** The test compares the static tuple with the names that `get_check_specs()` returns.
- **THEN** The two lists are equal, and the test names the first name that differs.

### Requirement: `--only` and `--skip` select a set of rows
`--only` and `--skip` SHALL accept a comma-separated list and a repeated option, and SHALL select exactly the named rows, so that the form `--only lint,format,domain` of `.pre-commit-config.yaml` keeps working.

#### Scenario: A comma-separated list of two rows
- **WHEN** The test runs the `ci` group with `--only constructs,openspec --dry-run`.
- **THEN** The run exits 0, and its request plan holds the commands of both rows and no command of another row.

#### Scenario: A repeated option
- **WHEN** The test runs the `ci` group with `--only constructs --only openspec --dry-run`.
- **THEN** The run exits 0, and its request plan holds the commands of both rows and no command of another row.

### Requirement: A wrong row name is a usage error with a close name
A row name that the registry does not hold MUST raise `BadParameter` from the option callback, with up to 3 close row names and the valid row names. The root group MUST record one usage error of kind `bad_value` with command path `ci`, and the run MUST exit 2.

#### Scenario: A misspelled row name of the only option
- **WHEN** The test runs the root CLI with `ci --only constructz`.
- **THEN** The run exits 2, its error text holds `constructs`, and the usage ledger holds one record of kind `bad_value` and command path `ci`.

#### Scenario: A misspelled row name of the skip option
- **WHEN** The test runs the root CLI with `ci --skip constructz`.
- **THEN** The run exits 2, and the usage ledger holds one record of kind `bad_value` and command path `ci`.

### Requirement: The help of the selection options names the rows
The help of `--only` and `--skip` MUST list the row names of the static tuple, so that a caller reads the valid names without a second command.

#### Scenario: A person reads the help of the group
- **WHEN** The test runs `devops ci --help`.
- **THEN** The help text of `--only` and of `--skip` holds each row name of the static tuple.

### Requirement: `devops ci run` is removed
`devops ci run` MUST NOT exist. The root group MUST report the word `run` as an unknown command and exit 2. The text of the removed command MUST NOT appear in `README.md`, in a file under `docs/` or `src/`, or in a test module other than the case that searches for it.

#### Scenario: The removed command
- **WHEN** The test runs the root CLI with `ci run`.
- **THEN** The run exits 2, and the usage ledger holds one record of kind `unknown_command` with command path `ci`.

#### Scenario: No other file names the removed command
- **WHEN** The test searches the tracked files with `git grep` and leaves its own module out.
- **THEN** The search finds no line.

### Requirement: The gate-slot metric description names no removed command
The description of the `CI_GATE_SLOT_WAIT` histogram SHALL be `Time a gate run waited for a free gate slot before its checks started`, which names no command and holds no removed command name.

#### Scenario: The description of the gate-slot histogram
- **WHEN** The test reads the description of `CI_GATE_SLOT_WAIT`.
- **THEN** The description equals `Time a gate run waited for a free gate slot before its checks started`.

### Requirement: The constructs row refuses the process-safety calls
The `constructs` row of `devops ci` SHALL report a violation for a `resource.setrlimit` call whose limit argument is `resource.RLIMIT_NPROC`, for `os.set_blocking` or `fcntl.fcntl` on a literal descriptor 0, 1 or 2 that sets it non-blocking, and for an `os.killpg` call outside the guard-holding functions of `src/devops_cli/core/process.py`. It SHALL report no violation for a literal descriptor above 2.

#### Scenario: A limit of RLIMIT_NPROC
- **WHEN** `devops ci --only constructs` runs on a module that calls `resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))`
- **THEN** ast-grep reports one violation at the call

#### Scenario: A standard descriptor set non-blocking
- **WHEN** `devops ci --only constructs` runs on a module that calls `os.set_blocking(0, False)` and `fcntl.fcntl(1, fcntl.F_SETFL, os.O_NONBLOCK)`
- **THEN** ast-grep reports one violation at each call

#### Scenario: A descriptor above 2
- **WHEN** `devops ci --only constructs` runs on a module that calls `os.set_blocking(3, False)` and `fcntl.fcntl(3, fcntl.F_SETFL, os.O_NONBLOCK)`
- **THEN** ast-grep reports no violation

#### Scenario: A bare process-group signal
- **WHEN** `devops ci --only constructs` runs on a module that calls `os.killpg(os.getpgid(pid), signal.SIGTERM)` at module level
- **THEN** ast-grep reports one violation at the call

#### Scenario: A guarded process-group signal
- **WHEN** `devops ci --only constructs` runs on a module whose guard-holding function calls `os.killpg(pgid, sig)`
- **THEN** ast-grep reports no violation

### Requirement: Each process-safety rule joins the construct gate
Each of the three process-safety rules SHALL set `severity: error`, SHALL name `src/**` in its `files`, and SHALL have one entry in `CONST_AST_GREP_RULE_FILES` and one in `VIOLATIONS` of the construct gate. Its case file SHALL hold a valid case and an invalid case.

#### Scenario: The rule set and the violation table
- **WHEN** `devops ci test tests/gate/construct_gate.py` reads the committed rule files and its violation table
- **THEN** It reports no missing rule, no rule outside the table, and no rule without a valid and an invalid case

### Requirement: A CLI start loads no pydantic and only the help catalog
A fresh interpreter that imports `devops_cli.dry_run.state` SHALL load neither `devops_cli.dry_run.models` nor `pydantic`. A fresh interpreter that imports `devops_cli.main` SHALL load no `pydantic` and SHALL build `devops_cli.lang.en.help` alone, with no `devops_cli.lang.en.messages` and no `devops_cli.lang.en.errors`.

#### Scenario: A start that imports the dry-run state
- **WHEN** a fresh interpreter imports `devops_cli.dry_run.state`
- **THEN** `devops_cli.dry_run.models` and `pydantic` are not in its modules

#### Scenario: A start that imports the CLI main
- **WHEN** a fresh interpreter imports `devops_cli.main`
- **THEN** `pydantic` is not in its modules

#### Scenario: A start that builds the help catalog
- **WHEN** a fresh interpreter imports `devops_cli.main`
- **THEN** `devops_cli.lang.en.messages` and `devops_cli.lang.en.errors` are not in its modules and `devops_cli.lang.en.help` is

### Requirement: A row line shows the name that --only and --skip take

The `devops ci` gate SHALL print each row line with its literal name in square brackets, escaped
so that Rich markup does not consume it. The name SHALL be the same string that `--only` and
`--skip` accept. The completed, skipped, timed-out, cancelled and `python_version` lines SHALL
carry it.

#### Scenario: A completed row shows its name

- **WHEN** a row completes and the gate prints its line
- **THEN** the line holds `[<name>]` and Rich renders the name as literal text

#### Scenario: A skipped row shows its name

- **WHEN** a row is skipped
- **THEN** the line holds `[<name>] skipped: <cause>`

#### Scenario: The printed name selects the row

- **WHEN** a user passes the printed name to `--only`
- **THEN** the gate runs that row and prints the same name again

#### Scenario: A name holds markup characters

- **WHEN** a row name holds brackets
- **THEN** the printed line holds the literal name and reads no part of it as markup

### Requirement: The table holds a hadolint row that runs the pre-commit hook
The table of `devops ci` SHALL hold a row `hadolint` whose command runs `uv run pre-commit run hadolint --all-files`.

#### Scenario: The row is the hadolint pre-commit hook
- **WHEN** `devops ci --only hadolint --dry-run` runs
- **THEN** the plan shows `uv run pre-commit run hadolint --all-files`

### Requirement: The kube-linter row lints the product base
The check registry of `devops ci` SHALL hold a row `kube-linter` whose command is `uv run devops k8s lint k8s/devops`, so that the row lints the build of the product base with the checks of `.kube-linter.yaml`. The row SHALL come before the rows of `tests/gate`.

#### Scenario: The row runs the lint of the product base
- **WHEN** a test reads the check spec of the row `kube-linter`
- **THEN** its command is `uv run devops k8s lint k8s/devops`, it has no other command, and it comes before the row `k8s` in the registry

### Requirement: The k8s row refuses a tracked environment file
The `k8s` row of `devops ci` SHALL fail when git tracks under `k8s/` a file that is not in `k8s/devops/` and is not a Markdown document, and SHALL name each such file. The check SHALL read the paths of the git index only, and no manifest.

#### Scenario: A tracked file outside the product base
- **WHEN** the rule reads a fixture git tree that tracks `k8s/llm/values.yaml`, `k8s/catalog.toml` and `k8s/devops-copy/service.yaml`
- **THEN** it names the three files

#### Scenario: The product base, a document and an untracked file
- **WHEN** the fixture tree tracks `k8s/devops/service.yaml` and `k8s/llm/README.md`, and holds an untracked file under `k8s/`
- **THEN** the rule names none of them

### Requirement: The k8s row refuses an in-cluster image registry in the product base
No object that a YAML file of `k8s/devops/` declares or that its kustomization renders SHALL run the Distribution image (Docker Hub's `registry`), be the Namespace `registry`, or be in namespace `registry`. The `k8s` row SHALL fail on such an object.

#### Scenario: The product objects
- **WHEN** `uv run devops ci --check --only k8s` runs
- **THEN** the row passes only when no object of the product base is one of these

### Requirement: The k8s row runs the offline lint of Argo on the Argo objects
The `k8s` row of `devops ci` SHALL run `argo lint --offline` on the objects of the rendered product base, and SHALL fail when the lint names a problem. The lint refuses each singular field that the Argo Workflows controller v4 refuses or does not read: `schedule` of a CronWorkflow, or `synchronization.mutex` or `synchronization.semaphore` of a Workflow spec or of one of its templates. A lint that cannot run SHALL fail the row.

#### Scenario: Each singular field gives one finding
- **WHEN** the check gives the lint one fixture object: a CronWorkflow with `spec.schedule`, a WorkflowTemplate with `spec.synchronization.mutex` or `spec.templates[0].synchronization.mutex`, a Workflow with `spec.synchronization.semaphore`, or a CronWorkflow with `spec.workflowSpec.synchronization.semaphore`
- **THEN** it gives one finding, and the finding names the kind and the name of the object and that field

#### Scenario: The plural fields and a CronJob give no finding
- **WHEN** the check gives the lint fixture objects with `schedules`, `mutexes` and `semaphores`, and a CronJob of `batch/v1` with `spec.schedule`
- **THEN** it gives no finding

#### Scenario: The product base
- **WHEN** `uv run devops ci --check --only k8s` runs
- **THEN** the row passes only when `argo lint --offline` names no problem in the Argo objects of `k8s/devops`
