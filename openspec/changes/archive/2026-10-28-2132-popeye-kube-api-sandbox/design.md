# Design

## Context

Since #2096, a review runs its tools in `SandboxToolExecutor`: bubblewrap with `--unshare-all`, so a tool has no network. Popeye is not a review tool. It reads the Kubernetes API, so it cannot run in a sandbox with no network. Decision 2 of #772 gives Popeye one named profile with the network that it needs, and the record of the run names the network. Issue #2132 makes that network the API server of the current context, with the kubeconfig read-only, and lets no other tool select the profile.

bubblewrap can only keep the network namespace of the host (`--share-net`) or make a new one with only a loopback device. The allow-lists of the sandbox apply only to the Docker engine and to Kubernetes. The sandbox thus needs another way to open one endpoint.

## Goals / Non-Goals

Goals:

- Popeye runs in the sandbox, with no network of its own, wherever it runs: `devops k8s audit`, the agent tool `scan_popeye` and the scanner registry.
- The sandbox reaches the API server of one context, and only to read. It sees no credential and no file of the user.
- Only Popeye can select the profile, and a test fails when another tool can.
- The record of a run names the network of the tool.
- `devops k8s audit` reports a pass only when Popeye ran.

Non-Goals:

- The context that `settings.k8s.context` names. Popeye uses the current context of the kubeconfig when its scan names none, as before. `resolve_context` of `src/devops_cli/k8s/context.py` is not in its path, and this change does not alter that.
- The scope of a Popeye scan. #2436 gives Popeye `-A` when a scan names no namespace, so Popeye scans every namespace, and `-n <namespace>` when a scan names one. This change keeps that command.
- A column for the network in the Tool Runs table of `review.md`. A review runs no tool with a network, so each row would say `none`. The field is in `profile.json` and in the SARIF property bag, as each field of the record is.

## Decisions

### 1. `kubectl proxy` outside the sandbox, `socat` in it

A shell outside the sandbox starts `kubectl proxy` on a Unix socket in a scratch directory. The proxy reads the kubeconfig and the credentials of the user, and sends each request to the API server of the context. The sandbox keeps `--unshare-all` and binds the scratch directory read-only. In the sandbox, `socat` listens on `127.0.0.1:8001` and relays each connection to the socket. Popeye reads a kubeconfig in the scratch directory that names `http://127.0.0.1:8001` and has no credentials.

The sandbox thus has a loopback device and one Unix socket, and the socket leads only to the API server. The credentials of the user stay outside the sandbox, so the guard of `_checked_bind` stays as it is. The kubeconfig that the sandbox binds read-only is the kubeconfig with no credentials, not the kubeconfig of the user.

Limits of the mechanism:

- The sandbox reaches every API path of the context that the credentials of the user can read, less the paths that the proxy refuses. RBAC of the cluster limits it further. The filter is that of `kubectl proxy`: a list of regular expressions that it matches against the decoded and cleaned path. It is a deny list, so a new subresource that reaches past the API server passes until `CONST_KUBE_API_REJECTED_PATHS` lists it.
- A process in the sandbox can read the responses of the API server, such as Secrets that the user can read. Popeye reads them in a direct run too.
- The proxy and the relay run for the time of one Popeye run only.

Rejected alternatives:

- `--share-net` with the kubeconfig of the user bound read-only. The sandbox then has every host and port that the host reaches, such as the LAN and the cloud metadata address. `_checked_bind` refuses each bind through `.kube` (`CONST_SANDBOX_SENSITIVE_SUBPATHS`), and a weaker guard is an escape. The kubeconfig of the user also holds the credentials of each context, and a kubeconfig can name certificate files and an exec plugin, which need more binds.
- The allow-lists of `SandboxNetworkConfig` (`public_whitelist`, `local_whitelist`, `egress_proxy`). They make a Docker network or a Kubernetes NetworkPolicy for a workload container (`src/devops_cli/sandbox/engine.py`). bubblewrap has no equal.
- `pasta` or `slirp4netns`. Neither is installed on this host. Both give the namespace a route to every address, with no allow-list for one destination.
- Landlock rules for TCP connections (Linux 6.7 and later). A rule names a port and not an address, and UDP has no rule. bubblewrap has no Landlock option, and `landrun` is not installed.
- `HTTPS_PROXY` for the client of Popeye. A proxy that Popeye reaches over TCP needs a route out of the namespace, and the namespace has none.
- A `kubectl proxy` that Python starts with `subprocess.Popen` and stops after the run. `core.process` has no call for a process that lives past one call, and the test floor refuses `kubectl` at `subprocess.Popen`. One command through `run_subprocess` keeps the one process seam (`process_fake`) and the wall-clock limit of the run.

### 2. The proxy is read-only

`kubectl proxy` gets `--reject-methods='(?i)^(POST|PUT|PATCH|DELETE)$'`. It also gets `--reject-paths` with its default paths (exec and attach of a pod), the port-forward of a pod, and the proxy subresource of a pod, a service and a node. A proxy subresource sends a request through the API server to a workload or a kubelet, which is more than the API server.

Evidence: Popeye 0.22.1 gave the same linters through the read-only proxy as in a direct run, and the proxy accepted each of its requests. A POST and a GET of the exec path of a pod through the relay got `403 Forbidden`.

### 3. One command, and the proxy ends with it

The executor starts one command through `run_subprocess`: `sh -c <host script>` with the socket, `setpriv`, `kubectl`, the context, the two filters, `socat` and the wait options, and then the bubblewrap command. The host script:

1. Starts `setpriv --pdeathsig KILL -- kubectl proxy ...` in the background, with its output on standard error.
2. Waits for the socket with `socat -u /dev/null UNIX-CONNECT:<socket>,retry=...,interval=...`, and stops the proxy and exits 1 when the socket does not come.
3. Runs bubblewrap, then stops the proxy and exits with the exit code of bubblewrap.

At the wall-clock limit, `subprocess.run` kills the shell. bubblewrap ends through `--die-with-parent`, and the proxy ends through `--pdeathsig`. So no process of the run stays, and the pipes of the run close.

In the sandbox, `sh -c <sandbox script>` starts the `socat` listener, waits for it with `socat ... TCP:127.0.0.1:8001,retry=...,interval=...`, and then runs `exec prlimit ... popeye ...`. When Popeye ends, bubblewrap ends its process namespace and the listener with it. Each program of the scripts has an absolute path. The PATH of the sandbox leads with the `.venv/bin` of the tree, and the tree could put a program there. Each `socat` runs with `-d0`, so it writes only errors.

### 4. The kubeconfig of the sandbox

The executor reads the context of the request, else the current context, with `kubectl config view --minify --output=json [--context=<name>]`, through `run_subprocess` as a local read. kubectl reads the kubeconfig as `kubectl proxy` then reads it: the files that `KUBECONFIG` names, else `~/.kube/config`. Its output redacts the credentials. The executor writes a JSON kubeconfig with one cluster, one context and one user, each with the name of the context. The cluster names `http://127.0.0.1:8001`. The user is empty. The context names no namespace: Popeye gets `-n <namespace>` or `-A` (#2436), so the namespace of a context has no effect on the scan. The proxy gets `--context=<name>`, so the proxy and the kubeconfig name the same context.

A kubeconfig that kubectl cannot read, or that has no such context, raises `SandboxError` with the first line of the error of kubectl, and the scan fails with its message. The proxy, the sandbox and the tool do not start.

The kubernetes Python client (`list_kube_config_contexts`) is not used. Its module has no type information, so its import needs one more `type: ignore`, and the count of these is at its ceiling. The client also reads `KUBECONFIG` only when it is imported. kubectl is a program of the relay already, and it reads the kubeconfig in the same way as the proxy.

### 5. Only Popeye selects the profile

`ToolRequest.network` is `KubeApiNetwork | None`. A validator refuses a `KubeApiNetwork` for a tool other than `popeye` (`CONST_TOOL_KUBE_API_TOOL`), and for a request that names a `program`, because a `program` can start another binary under the name `popeye`. `BaseSecurityScanner.tool_network` gives `None`, and `PopeyeScanner.tool_network` gives the profile for the context of the scan. `_run_built_command` gives that network to the request of the scan. A test runs every scanner of the registry and holds each to these rules. `SandboxToolExecutor.command` refuses a relay for a request that selects no profile, and a `kube-api` request with no relay. So a caller that holds a relay cannot give it to another tool.

`DirectToolExecutor` refuses a request that selects a network profile, with `SandboxError`. The direct executor gives a tool the whole network of the host, so it cannot give a profile, and a silent run with more network is a fail open. The refusal is in `record_tool_run`, for each executor that names a network of its own. So `ToolExecutorFake` with `network=host`, the fake that stands in for the direct executor, refuses the request in the same way, and the contract suite holds both to it.

### 6. The record names the network

`ToolRun.network` is `host` for `DirectToolExecutor`, `none` for a sandbox run with no profile, and the name of the profile, `kube-api`, for a sandbox run with it. `record_tool_run` takes the network from the request, and the direct executor gives `host`. Decision 2 of #772 says `network: allowed`. The name of the profile says more: which network the tool had.

### 7. Popeye runs in the sandbox, in an empty directory

`PopeyeScanner.__init__` makes a `SandboxToolExecutor` when it gets no executor. Every caller makes Popeye with no executor, so each runs Popeye in the sandbox. A host that cannot start the sandbox fails closed, as for a review: the scan reports a coverage gap that names the cause.

`run_popeye_scan` makes a new empty directory and scans it. The sandbox binds the tree of a request read-only and without `_checked_bind`, and Popeye reads no file of a tree. So the empty directory is the only tree that the sandbox shows. The `workdir` parameter goes.

Popeye 0.22.1 is built without cgo. It stops at start when it cannot find the user in `/etc/passwd` or in `$USER`. The sandbox binds `/etc/passwd` read-only for Popeye through `CONST_TOOL_HOST_READ_ONLY_PATHS`, the table that already gives Semgrep its CA certificates. The file holds no secret.

### 8. `devops k8s audit` says when Popeye did not run

The command checks the status of the outcome, as `devops k8s lint` does. For a status other than `ran`, it prints the status and the reason, reports no pass and exits 1.

## Risks / Trade-offs

- The host needs `socat`, `kubectl` and `setpriv`. A host without one of them runs no Popeye scan, and the scan names the program. The devcontainer image installs `socat`. `setpriv` is in util-linux, as `prlimit` is.
- The two shell scripts are product code that only a run on a host with a cluster tests in full. The tests hold their arguments, and a person can run `devops k8s audit` on a cluster to see the scripts work.
- The `network` field adds one key to each record in `profile.json` and in `findings.sarif`. The field is required. A `profile.json` that a review wrote before this change has records with no `network`, so `ReviewProfile.load` reads it as no profile, and `devops review stats`, the review score and the history leave that session out. devops-cli keeps no backward compatibility before 1.0.0, so the change adds no default for old records.
