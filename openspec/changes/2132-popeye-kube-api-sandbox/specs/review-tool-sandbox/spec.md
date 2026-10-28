## ADDED Requirements

### Requirement: Only Popeye selects the kube-api network profile
The sandbox SHALL have one network profile, `kube-api`, which a `ToolRequest` selects with `network`. A request SHALL be refused when it selects `kube-api` for a tool other than `popeye`, or when it selects `kube-api` and names a `program`.

#### Scenario: Another tool selects the profile
- **WHEN** a request for the tool of any scanner of the scanner registry other than Popeye selects `kube-api`
- **THEN** the request is refused

#### Scenario: Popeye from another program
- **WHEN** a request for `popeye` selects `kube-api` and names a program
- **THEN** the request is refused

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
The tool of a `kube-api` request SHALL get `KUBECONFIG` set to a kubeconfig in the scratch directory that names `http://127.0.0.1:8001`, the name and the namespace of the context, and no credentials. The scratch directory SHALL not stay after the run. A context that the kubeconfig of the user does not have SHALL stop the run before anything starts.

#### Scenario: The kubeconfig in the sandbox
- **WHEN** the kubeconfig of the user has the active context `example` with the namespace `apps`, a cluster at `https://192.0.2.10:6443` and a user with a token
- **THEN** during the run, the kubeconfig in the scratch directory names `http://127.0.0.1:8001`, the context `example` with the namespace `apps`, and a user with no field
- **AND** after the run, the scratch directory does not exist

#### Scenario: A context that the kubeconfig does not have
- **WHEN** the request selects `kube-api` for a context that the kubeconfig of the user does not have, or the user has no kubeconfig
- **THEN** the run raises `SandboxError` and starts nothing

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
