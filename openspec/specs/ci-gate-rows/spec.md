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

### Requirement: The roadmap-stage-eval-commits row checks the base commit of each golden case
The table of `devops ci` SHALL hold a row `roadmap-stage-eval-commits` that runs the check module of the row from `tests/gate/`. The row SHALL read the golden stage eval cases and the git history of the repository, and it SHALL pass when each base commit that is not `NO_COMMIT` is a full hash that names a commit of the repository.

#### Scenario: The row reads the cases and the history
- **WHEN** `devops ci` runs the `roadmap-stage-eval-commits` row
- **THEN** the row reads the golden cases and the git history of the repository and prints the count of cases that it read

#### Scenario: The golden set passes the row
- **WHEN** each case whose base commit is not `NO_COMMIT` names a full hash of a commit of the repository, and each other case has a note that says it reads no commit
- **THEN** the row passes and prints the count of cases that it read

### Requirement: The roadmap-stage-eval-commits row fails on a base commit that it cannot resolve
The row SHALL fail and SHALL name each case whose base commit is not a full hash of a commit of the repository, and each case whose base commit is `NO_COMMIT` and whose notes do not say that it reads no commit.

#### Scenario: Base commit is no commit
- **WHEN** a case names a 40-character hash that `git cat-file -e` cannot resolve as a commit
- **THEN** the row fails and its message names the case and the hash

#### Scenario: A case with no commit lacks the note
- **WHEN** a case has base commit `NO_COMMIT` and no note that says it reads no commit
- **THEN** the row fails and its message names the case

### Requirement: The roadmap-stage-eval-commits row fails on a shallow clone
The row SHALL fail when the repository is a shallow clone, with a message that says the clone lacks the history that the golden cases name. The `static` job of `.github/workflows/ci.yml`, which runs the row, SHALL check out the full history with `fetch-depth: 0`.

#### Scenario: Shallow repository
- **WHEN** `git rev-parse --is-shallow-repository` prints `true`
- **THEN** the row fails and the message says that the shallow clone lacks the history that the golden cases need

#### Scenario: The Static Analysis job gives the row the full history
- **WHEN** a test reads the `Check out repository` step of the `static` job in `.github/workflows/ci.yml`
- **THEN** the step sets `fetch-depth: 0`
