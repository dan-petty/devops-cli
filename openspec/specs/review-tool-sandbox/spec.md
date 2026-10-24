# review-tool-sandbox Specification

## Purpose
A review runs the tools that read the reviewed tree in a sandbox with no network, a cleared environment, a read-only tree and limits, so that a tool started on an untrusted tree reaches nothing else on the host.

## Requirements

### Requirement: A review runs its tools in the sandbox and in no other place
`devops review path`, `devops review branch` and `devops review pr`, and their MCP tools, SHALL run every analyzer, evidence tool and canary of the review in `SandboxToolExecutor`. An orchestrator, a mypy scan and a canary that get no executor SHALL run their tools in `SandboxToolExecutor`. No option, config key or MCP parameter SHALL turn the sandbox off. The record of each run SHALL name the executor `sandbox`.

#### Scenario: A review that gets no executor
- **WHEN** an orchestrator that got no executor scans a Python file on a host that can start the sandbox
- **THEN** each command that starts a tool starts bubblewrap with the tool in it
- **AND** the record of each run names the executor `sandbox`

#### Scenario: A dry run
- **WHEN** a scan of Bandit, Gitleaks, Semgrep, Trivy, kube-linter, Pluto, osv-scanner, Ruff or mypy runs in a dry run
- **THEN** it starts no tool and gives its dry-run outcome

### Requirement: The sandbox executor checks the host one time and fails closed
Before its first run, the sandbox executor SHALL check one time that bubblewrap and `prlimit` are installed and that bubblewrap can start `prlimit -- true` in a sandbox. On a host that fails the check, each run SHALL raise `SandboxUnavailableError` with the cause, and no tool SHALL start, in the sandbox or outside it.

#### Scenario: No bubblewrap, no prlimit or no user namespace
- **WHEN** bubblewrap or `prlimit` is not installed, or bubblewrap ends the check with `bwrap: setting up uid map: Permission denied`
- **THEN** a run raises `SandboxUnavailableError` with the cause, and a second run raises it again with no second check
- **AND** no command starts but the check

### Requirement: A review on a host that cannot start the sandbox reports a gap for each tool
When the host cannot start the sandbox, each scan SHALL report a coverage gap whose reason names the cause, and a canary that did not run SHALL withhold no finding. The review SHALL say the cause, and what a person can change on the host, one time, and SHALL run no tool outside the sandbox.

#### Scenario: The scans of a review on such a host
- **WHEN** a review of a Python file runs on a host whose kernel refuses bubblewrap a user namespace
- **THEN** Bandit, Gitleaks and Semgrep each report a coverage gap whose reason names the cause
- **AND** the review holds no tool run and no canary result
- **AND** the review workflow prints one time that its tools did not run, the cause, and what a person can change on the host, and offers no run outside the sandbox

#### Scenario: Each scan on such a host
- **WHEN** a scan of Bandit, Gitleaks, Semgrep, Trivy, kube-linter, Pluto, osv-scanner, Ruff or mypy gets an executor that cannot start the sandbox
- **THEN** the scan reports a coverage gap with no findings, and its reason names the cause

### Requirement: The sandbox binds the program of a tool and what it reads when it starts
The sandbox SHALL bind the program of a tool read-only: the virtualenv that holds it in its `bin`, else the program file. It SHALL bind the host paths that a tool reads when it starts, such as `/etc/ssl/certs` for Semgrep, read-only.

#### Scenario: The program of a tool
- **WHEN** the program of a tool is one file outside the system directories, or the program is in the `bin` of a virtualenv
- **THEN** the sandbox binds that file, or that virtualenv, read-only

#### Scenario: The CA certificates of Semgrep
- **WHEN** the sandbox runs Semgrep on a host that has `/etc/ssl/certs`
- **THEN** it binds `/etc/ssl/certs` read-only, and it binds no such path for Gitleaks

### Requirement: A virtualenv outside the tree brings its Python installation
For each read-only bind that is a virtualenv, the sandbox SHALL bind the Python installation that its `python` links to, at its own path and at the path that the link names. It SHALL bind only an installation that holds the standard library, holds neither the home directory nor the tree, and passes through no credential directory.

#### Scenario: A virtualenv outside the tree, made by uv
- **WHEN** a read-only bind is a virtualenv whose `python` links to `cpython-3.14/bin/python3.14`, and `cpython-3.14` links to the installation `cpython-3.14.7`
- **THEN** the sandbox binds the virtualenv, and binds `cpython-3.14.7` read-only at its own path and at the path of `cpython-3.14`

#### Scenario: An installation that the repository aims elsewhere
- **WHEN** the `python` of such a virtualenv links into the home directory, into a credential directory, or to a prefix with no standard library
- **THEN** the sandbox binds the virtualenv and no installation

### Requirement: The sandbox refuses a bind that shows too much
A read-only or writable bind whose resolved path holds the home directory or the tree, or passes through a credential directory, SHALL be refused, and nothing SHALL start.

#### Scenario: A bind that shows too much
- **WHEN** a read-only or a writable bind is the home directory, a directory above the tree, or a directory below `.ssh`
- **THEN** the sandbox refuses the command

### Requirement: The sandbox binds the directories that a tool writes read-write
A `ToolRequest` SHALL name in `writable_dirs` the directories that its tool writes and that stay after the run, and the sandbox SHALL bind each one read-write, after the read-only binds. The mypy scan and the mypy canary SHALL name their cache directory there and through `MYPY_CACHE_DIR`. The command of the mypy canary SHALL hold no `--cache-dir`.

#### Scenario: The cache of a mypy scan
- **WHEN** a review runs mypy
- **THEN** the request names its cache directory, outside the tree, in `MYPY_CACHE_DIR` and in `writable_dirs`

#### Scenario: The cache of the mypy canary
- **WHEN** the canary of mypy runs
- **THEN** its request names the directory `mypy_cache` of its scratch directory in `MYPY_CACHE_DIR` and in `writable_dirs`, and its arguments hold no `--cache-dir`

### Requirement: Each tool gets the address space and the data that it needs
Gitleaks SHALL get an address space of 8 GiB and Semgrep one of 16 GiB, and every other tool SHALL get 2 GiB. Every Semgrep scan and the Semgrep canary SHALL run four jobs. A Trivy scan SHALL name the Trivy cache in `TRIVY_CACHE_DIR` and bind it read-only, and an osv-scanner scan SHALL name the directory of its offline database in `OSV_SCANNER_LOCAL_DB_CACHE_DIRECTORY` and bind its `osv-scalibr` directory read-only, when it exists.

#### Scenario: The limits of Gitleaks and Semgrep
- **WHEN** a review scans with Gitleaks and Semgrep
- **THEN** the request of Gitleaks has an address space of 8 GiB, the request of Semgrep has 16 GiB, and the command of Semgrep holds `--jobs 4`

#### Scenario: A fetched database
- **WHEN** the Trivy cache or the `osv-scalibr` directory of osv-scanner exists
- **THEN** the request names the directory by the variable of the tool and binds what the tool reads there read-only

### Requirement: A Ruff scan keeps its cache of the tree outside the tree
A Ruff scan SHALL keep its cache in a directory of the tree, outside the tree, which the request names in `RUFF_CACHE_DIR` and in `writable_dirs`. The Ruff canary SHALL run with `--no-cache`.

#### Scenario: Two scans of one tree and a scan of another
- **WHEN** a review scans one tree with Ruff two times, and another tree one time
- **THEN** both requests of the tree name one cache directory, outside the tree, in `RUFF_CACHE_DIR` and in `writable_dirs`, and the request of the other tree names another directory
- **AND** no command of the scans holds `--no-cache`

#### Scenario: The Ruff canary
- **WHEN** the canary of Ruff runs
- **THEN** its command holds `--no-cache`

### Requirement: A mypy run that did not check its files fails
A mypy scan SHALL fail with the exit code and the error of mypy when mypy ends with an exit code other than 0 or 1.

#### Scenario: A mypy that did not start
- **WHEN** the executor answers a mypy run with exit code 2 or 127
- **THEN** the scan fails with `mypy exited with code <code>: <error>`
