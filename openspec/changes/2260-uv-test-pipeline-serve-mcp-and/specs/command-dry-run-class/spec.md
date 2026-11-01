## ADDED Requirements

### Requirement: uv-request-plans
The four commands `uv lock`, `uv python-install`, `uv run` and `uv sync` SHALL carry the `request-plan` dry-run class and expose `--dry-run`. Under `--dry-run` each command SHALL start no process and SHALL print one request. That request SHALL hold the argument list of the real run, with the uv preview features that the process runner adds.

#### Scenario: Dry run on uv sync
- **WHEN** a user runs `devops uv sync --frozen --dry-run` or `devops --dry-run uv sync --frozen`
- **THEN** no process starts and the plan prints one request whose argument list is `uv --preview-features malware-check,check-command sync --frozen`

#### Scenario: Dry run on uv run keeps the tokens after the separator
- **WHEN** a user runs `devops --dry-run uv run -- pytest --dry-run`
- **THEN** no process starts and the plan prints one request whose argument list ends with `run pytest --dry-run`

#### Scenario: The plan matches the real run
- **WHEN** a test runs `devops uv lock --upgrade` against a process fake that records each call
- **THEN** the recorded argument list equals the argument list of the plan that `devops uv lock --upgrade --dry-run` prints

### Requirement: pipeline-request-plans
The command `pipeline` SHALL carry the `request-plan` dry-run class. Under `--dry-run` it SHALL start no process, print one `dagger call` request built by `build_dagger_cmd`, and print no simulated result.

#### Scenario: Dry run on pipeline
- **WHEN** a user runs `devops pipeline <dir> --function build --dry-run` or `devops --dry-run pipeline <dir> --function build`, where `<dir>` is a directory that exists
- **THEN** no process starts and the plan prints one request that starts with `dagger call -m` and names the function `build`

### Requirement: test-request-plans
The commands `test load`, `test run` and `test sandbox` SHALL carry the `request-plan` dry-run class. Under `--dry-run` each command SHALL make no request and print the requests of the real run: one `k6 run` request for `test load`, one `uv run pytest` request for `test run`, and the container lifecycle requests of `docker sandbox` for `test sandbox`. `test sandbox` SHALL refuse a forbidden workspace before it prints the plan.

#### Scenario: Dry run on test load
- **WHEN** a user runs `devops test load smoke.js --vus 5 --duration 5s --dry-run`
- **THEN** no process starts and the plan prints one request `k6 run` with `--vus 5` and `--duration 5s`, and no simulated metrics

#### Scenario: Dry run on test run
- **WHEN** a user runs `devops --dry-run test run tests/unit -x -k parse`
- **THEN** no process starts and the plan prints one request `uv run pytest -x -k parse tests/unit` with the uv preview features

#### Scenario: Dry run on test sandbox
- **WHEN** a user runs `devops test sandbox --dry-run --workspace <dir> echo hi` with the Docker client patched to fail
- **THEN** no Docker client is built and the plan prints `DOCKER POST /containers/create` followed by the start, wait, logs and remove requests

#### Scenario: Dry run on test sandbox with a forbidden workspace
- **WHEN** a user runs `devops test sandbox --dry-run --workspace /` with the Docker client patched to fail
- **THEN** the command refuses the workspace, exits with the error status, and prints no plan

### Requirement: test-profile-memory-local-preview
The command `test profile-memory` SHALL carry the `no-external-request` dry-run class and expose `--dry-run`. Under `--dry-run` it SHALL run no profiler, import no module and write no file. It SHALL print the target, the iteration count, the limits and the path of the report that the run would write.

#### Scenario: Dry run on profile-memory with a custom target
- **WHEN** a user runs `devops test profile-memory example.module:work --output report.json --dry-run` with the module import patched to fail
- **THEN** the preview names the target and the path `report.json`, no module is imported and no file is written

### Requirement: mcp-local-preview
The command `mcp export-schemas` SHALL carry the `no-external-request` dry-run class and expose `--dry-run`. Under `--dry-run` it SHALL print the directory and the number of tool schemas that it would export, create no directory and write no file.

#### Scenario: Dry run on mcp export-schemas
- **WHEN** a user runs `devops mcp export-schemas --output-dir <dir> --dry-run` with directory creation and file writes patched to fail
- **THEN** the preview prints `<dir>` and the tool count, and nothing is created

### Requirement: mcp-tools-no-external-request
The command `mcp tools` SHALL carry the `no-external-request` dry-run class and declare no `--dry-run` option, so `devops --dry-run mcp tools` runs it as it is.

#### Scenario: Dry run on mcp tools
- **WHEN** a user runs `devops --dry-run mcp tools` with the process runner and the HTTP clients patched to fail
- **THEN** the command prints the table of tools and starts no process

### Requirement: server-request-plans
The commands `mcp serve` and `serve` SHALL carry the `request-plan` dry-run class and expose `--dry-run`. Under `--dry-run` each command SHALL start no server and open no socket. It SHALL print a bind request and a start request built from the values of the real call. `mcp serve --transport sse` SHALL refuse a host that is not loopback without `--allow-remote`, as the real run does. `serve --service --dry-run` SHALL load no settings and read no credential.

#### Scenario: Dry run on mcp serve over sse
- **WHEN** a user runs `devops mcp serve --transport sse --host 127.0.0.1 --port 9090 --dry-run` with `run_mcp_server` patched to fail
- **THEN** the plan prints a bind request for `127.0.0.1:9090` and a start request for the `sse` transport

#### Scenario: Dry run on mcp serve with a remote host
- **WHEN** a user runs `devops mcp serve --transport sse --host 192.0.2.10 --dry-run`
- **THEN** the command refuses the host as the real run does and prints no plan

#### Scenario: Dry run on serve
- **WHEN** a user runs `devops --dry-run serve --host 127.0.0.1 --port 9000 --workers 2` with `uvicorn.run` patched to fail
- **THEN** the plan prints a bind request for `127.0.0.1:9000` and a start request that names 2 workers

### Requirement: ci-fail-to-pass-request-plans
The command `ci fail-to-pass`, and the paths `format fail-to-pass` and `lint fail-to-pass` that share its callback, SHALL carry the `request-plan` dry-run class. Under `--dry-run` the command SHALL start no process, git call included. It SHALL print the ordered requests of the replay, built by the argument builders that the replay uses, with the placeholders `<merge-base>`, `<tree>` and `<changed test files>`.

#### Scenario: Dry run on ci fail-to-pass
- **WHEN** a user runs `devops ci fail-to-pass --base main --dry-run` with the process fake patched to fail on any call
- **THEN** the plan prints the merge base, the two revision checks, the diff, the untracked-file listing (`git ls-files --others`), the worktree add, the archive, the pytest replay, the worktree remove and the worktree prune requests in that order, and no process starts

#### Scenario: The plan matches the replay
- **WHEN** a test runs the replay against a process fake that records each call
- **THEN** each recorded argument list equals the matching request of the plan after the placeholders are replaced
