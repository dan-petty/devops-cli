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

### Requirement: Only Popeye selects the kube-api network profile
The sandbox SHALL have one network profile, `kube-api`, which a `ToolRequest` selects with `network`. A request SHALL be refused when it selects `kube-api` for a tool other than `popeye`, or when it selects `kube-api` and names a `program`. The sandbox executor SHALL refuse to build the command of a request that selects no network profile with a relay to the API server, and of a request that selects `kube-api` with no relay.

#### Scenario: Another tool selects the profile
- **WHEN** a request for the tool of any scanner of the scanner registry other than Popeye selects `kube-api`
- **THEN** the request is refused

#### Scenario: Popeye from another program
- **WHEN** a request for `popeye` selects `kube-api` and names a program
- **THEN** the request is refused

#### Scenario: A relay for a request with no profile
- **WHEN** the sandbox executor builds the command of a Gitleaks request with the relay of a `kube-api` run
- **THEN** it raises `SandboxError` and starts nothing

### Requirement: Each scanner names the network of its scan
Every scanner of the scanner registry other than Popeye SHALL select no network. Popeye SHALL select `kube-api` for the context of its scan, and for the current context when the scan names none or names `current`.

#### Scenario: The network of each scanner
- **WHEN** each scanner of the scanner registry gives the network of a scan of the context `example`
- **THEN** Popeye gives `kube-api` for the context `example`, and every other scanner gives no network

### Requirement: The direct executor runs no network profile
The direct executor SHALL refuse a request that selects a network profile, and start nothing.

#### Scenario: The direct executor and the profile
- **WHEN** the direct executor gets a Popeye request that selects `kube-api`
- **THEN** it raises `SandboxError` and starts nothing

### Requirement: A kube-api run reaches the API server only through a read-only proxy
The sandbox executor SHALL run a request that selects `kube-api` as one command. Outside the sandbox, that command SHALL start `kubectl proxy` under `setpriv --pdeathsig KILL`, on a Unix socket in a scratch directory, for the context of the request. The proxy SHALL refuse the methods POST, PUT, PATCH and DELETE, and the exec, attach, port-forward and proxy paths.

#### Scenario: The command outside the sandbox
- **WHEN** the sandbox executor runs a Popeye request that selects `kube-api` for the context `example`
- **THEN** the command starts the host script with the socket, `setpriv`, `kubectl`, `example`, the two filters and `socat`, then bubblewrap

### Requirement: A kube-api sandbox has no network of its own
The sandbox of a `kube-api` request SHALL keep `--unshare-all` with no `--share-net`, SHALL bind the scratch directory read-only, and SHALL relay `127.0.0.1:8001` to the socket with `socat` before the tool starts under `prlimit`.

#### Scenario: The command in the sandbox
- **WHEN** the sandbox executor runs a Popeye request that selects `kube-api`
- **THEN** bubblewrap runs with `--unshare-all` and no `--share-net`, binds the scratch directory read-only, and starts the sandbox script with `socat`, the socket and the port 8001, then `prlimit` and Popeye

### Requirement: A kube-api tool gets a kubeconfig with no credentials
The tool of a `kube-api` request SHALL get `KUBECONFIG` set to a kubeconfig in the scratch directory that names `http://127.0.0.1:8001` and the name of the context, with no namespace and no credentials. The executor SHALL read the name of the context with `kubectl config view --minify`. The scratch directory SHALL not stay after the run. A context that the kubeconfig of the user does not have SHALL stop the run before the proxy, the sandbox or the tool starts.

#### Scenario: The kubeconfig in the sandbox
- **WHEN** the kubeconfig of the user has the active context `example` with the namespace `apps`, a cluster at `https://192.0.2.10:6443` and a user with a token
- **THEN** during the run, the kubeconfig in the scratch directory names `http://127.0.0.1:8001`, the context `example` with no namespace, and a user with no field
- **AND** after the run, the scratch directory does not exist

#### Scenario: A context that the kubeconfig does not have
- **WHEN** the request selects `kube-api` for a context that the kubeconfig of the user does not have, or the user has no kubeconfig
- **THEN** the run raises `SandboxError` with the error of kubectl, and starts no proxy, no sandbox and no tool

### Requirement: A host without a program of the relay runs no kube-api request
A `kube-api` run SHALL raise `SandboxUnavailableError` that names the program, and start nothing, when `sh`, `socat`, `kubectl` or `setpriv` is not installed.

#### Scenario: A host without socat
- **WHEN** `socat` is not installed
- **THEN** a `kube-api` run raises `SandboxUnavailableError` that names `socat`, and starts nothing

### Requirement: Popeye reads the user database of the host
The sandbox SHALL bind `/etc/passwd` read-only for Popeye, and for no other tool, because Popeye stops at start when it cannot find the user.

#### Scenario: The binds of a Popeye run
- **WHEN** the sandbox executor runs a Popeye request, and a request of another tool
- **THEN** bubblewrap binds `/etc/passwd` read-only for Popeye, and not for the other tool

### Requirement: A golangci-lint scan reads the Go toolchain and the module cache from go env
Before a golangci-lint scan, the scanner SHALL read the toolchain and the module cache of the host with `go env -json GOROOT GOMODCACHE`, started outside the tree with `GOTOOLCHAIN=local`. A `go env` that fails SHALL give a failed scan that starts no golangci-lint.

#### Scenario: The go env of a scan
- **WHEN** golangci-lint scans a Go module
- **THEN** `go env -json GOROOT GOMODCACHE` starts outside the module with `GOTOOLCHAIN=local`

#### Scenario: A host whose go env fails
- **WHEN** `go env` exits with an error before a golangci-lint scan
- **THEN** the scan fails, starts no golangci-lint, and its reason names `go env`

### Requirement: golangci-lint gets the Go toolchain, the module cache and its caches, and no network
The request of golangci-lint SHALL name the toolchain in `GOROOT`, bind it read-only, and put its `bin` first on the `PATH`. It SHALL name the module cache in `GOMODCACHE` and bind it read-only when it exists. It SHALL name a Go build cache in `GOCACHE` and a golangci-lint cache in `GOLANGCI_LINT_CACHE`, both outside the tree, in `writable_dirs`. It SHALL set `GOPROXY=off` and `GOTOOLCHAIN=local`, SHALL set no `GOFLAGS`, and SHALL select no network profile.

#### Scenario: A scan of a Go module
- **WHEN** golangci-lint scans a Go module on a host whose `go env` names a toolchain and a module cache that exist
- **THEN** the request binds the toolchain and the module cache read-only, names them in `GOROOT` and `GOMODCACHE`, and puts the `bin` of the toolchain first on the `PATH`
- **AND** the request names `GOCACHE` and `GOLANGCI_LINT_CACHE`, two directories outside the module, in `writable_dirs`
- **AND** the request sets `GOPROXY=off` and `GOTOOLCHAIN=local`, sets no `GOFLAGS`, and selects no network profile

### Requirement: A Go module whose modules are not in the module cache is a coverage gap
A golangci-lint run that ends with an error because the `go` command finds a module neither in the module cache nor on a proxy (`module lookup disabled by GOPROXY=off`) SHALL give a coverage gap with no findings. Its reason SHALL name the module cache and `go mod download`. Another error that stops the run SHALL still give a failed scan.

#### Scenario: A host with no module cache
- **WHEN** golangci-lint scans a Go module that requires another module, on a host whose module cache does not exist, and the run ends with `module lookup disabled by GOPROXY=off`
- **THEN** the request binds no module cache
- **AND** the scan reports a coverage gap with no findings, and its reason names the module cache and `go mod download`

#### Scenario: A typecheck error
- **WHEN** the run of golangci-lint ends with a typecheck error
- **THEN** the scan fails, and its reason quotes the error
