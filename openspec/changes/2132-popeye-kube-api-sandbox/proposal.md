# Proposal

## Why

Issue #2132, decision 2 of the tracker #772: Popeye ran with no sandbox. `devops k8s audit` calls `run_popeye_scan`, which made `PopeyeScanner()` with no executor, so `BaseSecurityScanner` gave it a `DirectToolExecutor`. The agent tool `scan_popeye` and the global `ScannerRegistry` made Popeye the same way. Popeye thus ran as a child process of devops-cli, with the environment, the files and the whole network of the user.

Popeye reads the Kubernetes API, so it cannot run in the sandbox with no network. Decision 2 gives Popeye one named network profile that no other tool can select, and the record of the run names the network.

Two more defects stand in the path of the fix:

- Popeye started in the directory that the caller gave: the working directory of `devops k8s audit`, or the workspace of the agent. The sandbox binds the tree of a request read-only, so a run from the home directory would show the home directory, with `.kube` and `.ssh`, to Popeye. Popeye reads no file of a tree.
- When Popeye did not run, `devops k8s audit` printed "Popeye cluster audit passed" and exited 0, because it read only the list of findings. A sandbox that fails closed makes this false pass more frequent.

## What Changes

- The tool sandbox gets one network profile, `kube-api`. A `ToolRequest` selects it with `network=KubeApiNetwork(context=...)`. The request refuses the profile for any tool other than `popeye`, and for a request that names a `program`. `BaseSecurityScanner.tool_network` selects no network, and only `PopeyeScanner` selects `kube-api`, for the context of its scan. `DirectToolExecutor` refuses a request that selects a network profile, and so does `ToolExecutorFake` with `network=host`, the fake that stands in for it. `SandboxToolExecutor.command` refuses a relay for a request that selects no profile.
- `SandboxToolExecutor` runs a `kube-api` request as one command through `run_subprocess`:
  - A shell outside the sandbox starts `kubectl proxy --unix-socket=<scratch>/kube-api.sock --context=<context>` under `setpriv --pdeathsig KILL`. `kubectl proxy` reads the kubeconfig and the credentials of the user outside the sandbox. It refuses the methods POST, PUT, PATCH and DELETE, and the exec, attach, port-forward and proxy paths. The shell waits for the socket, starts bubblewrap, and stops the proxy when bubblewrap ends.
  - bubblewrap keeps `--unshare-all`, so the sandbox has no network of its own. It binds the scratch directory read-only. In the sandbox, a shell starts `socat`, which listens on `127.0.0.1:8001` and relays each connection to the socket. Popeye then starts under `prlimit`, with `KUBECONFIG` set to the kubeconfig in the scratch directory. That kubeconfig has no credentials. It names `http://127.0.0.1:8001` and the name of the context, and no namespace.
  - The executor reads the name of the context from the kubeconfig of the user with `kubectl config view --minify`, which reads the kubeconfig as the proxy reads it and redacts the credentials. A host without `sh`, `socat`, `kubectl` or `setpriv` fails closed with `SandboxUnavailableError`, which names the program. A context that the kubeconfig does not have raises `SandboxError`.
- The record of each run (`ToolRun`) gets the field `network`: `host` for the direct executor, `none` for the sandbox, and `kube-api` for the profile.
- `PopeyeScanner` runs in `SandboxToolExecutor` when it gets no executor. So `devops k8s audit`, the agent tool `scan_popeye` and the scanner registry run Popeye in the sandbox with the `kube-api` profile. The sandbox binds `/etc/passwd` read-only for Popeye (`CONST_TOOL_HOST_READ_ONLY_PATHS`), because Popeye stops at start when it cannot find the user.
- `run_popeye_scan` takes no `workdir`, and loses its unused `save_output`. Popeye starts in a new empty directory, the only tree that the sandbox shows it. The agent tool `scan_popeye` no longer checks the working directory against the workspace, because Popeye does not start there.
- `devops k8s audit` says that the audit did not run, with the status and the reason, and exits 1, when Popeye did not run. It reports a pass only when Popeye ran and found nothing, as `devops k8s lint` does.
- The devcontainer image installs `socat`.
- `SECURITY.md`, `docs/SELF_IMPROVEMENT.md`, `docs/DEVCONTAINER_USAGE.md`, `docs/TESTING.md` and the docstrings of `src/devops_cli/security/tool_executor.py` describe the profile, the `network` field and the new default of Popeye.
- The change alters what `devops k8s audit`, the agent tool `scan_popeye` and the record of a tool run do and show, so it carries spec deltas.

## Capabilities

### New Capabilities

- `k8s-audit`: `devops k8s audit` runs Popeye in the sandbox with the `kube-api` profile, and fails when Popeye did not run.

### Modified Capabilities

- `review-tool-sandbox`: the sandbox has one network profile, `kube-api`, that only Popeye selects, and that reaches only the API server of one context, only to read.
- `review-tool-runs`: the record of a run names the network of the tool.
- `agent-scan-tools`: `scan_popeye` runs Popeye in an empty directory, in the sandbox.

## Impact

- Code: `src/devops_cli/security/tool_executor.py`, `src/devops_cli/sandbox/kube_api.py` (new), `src/devops_cli/security/base.py`, `src/devops_cli/security/dive.py`, `src/devops_cli/security/popeye.py`, `src/devops_cli/commands/k8s/security_audit.py`, `src/devops_cli/ai/tools/builtin_tools.py`, `src/devops_cli/config/constants.py` and `src/devops_cli/lang/en/messages.py`.
- Tests: `tests/security/test_kube_api_network_profile.py` (new), `tests/commands/test_k8s_audit.py` (new), `tests/test_secops.py`, `tests/test_builtin_tools.py`, `tests/test_k8s.py`, `tests/test_security_sarif.py`, `tests/test_tool_executor_contract.py`, `tests/support/fakes/tool_executor.py` and `tests/support/fakes/scanners.py`.
- Build: `.devcontainer/Dockerfile`.
- Documentation: `SECURITY.md`, `docs/SELF_IMPROVEMENT.md`, `docs/DEVCONTAINER_USAGE.md` and `docs/TESTING.md`.
- The change fits one pull request.

## Feasibility

- Code, at `origin/main` `d739a472`: `run_popeye_scan` in `src/devops_cli/security/popeye.py` makes `PopeyeScanner()` with no executor. `BaseSecurityScanner.__init__` then makes a `DirectToolExecutor`. `_create_default_scanners` in `src/devops_cli/security/registry.py` makes `PopeyeScanner()` too, and `scan_popeye` in `src/devops_cli/ai/tools/builtin_tools.py` calls `run_popeye_scan`. The premise is correct.
- Command output, `bwrap --help` of bubblewrap 0.13.1: the only network options are `--share-net` (the whole network of the host) and `--unshare-net` (only a loopback device). bubblewrap has no egress filter. `HostSandbox.build_bwrap_args` always passes `--unshare-all`.
- Code: the egress allow-lists of the sandbox (`SandboxNetworkConfig` in `src/devops_cli/sandbox/models.py`, the modes `public_whitelist` and `local_whitelist`, and `egress_proxy`) apply only to a container of the Docker engine (`src/devops_cli/sandbox/engine.py`) and to a Kubernetes NetworkPolicy. They do not apply to bubblewrap. So the existing sandbox has no narrower network for a bubblewrap run. The mechanism of this change is a relay: `kubectl proxy` outside the sandbox on a Unix socket, and `socat` in the sandbox on the loopback device.
- Code: `_checked_bind` in `src/devops_cli/sandbox/host.py` refuses every bind that passes through a directory of `CONST_SANDBOX_SENSITIVE_SUBPATHS`, which holds `.kube`. So the sandbox cannot bind the kubeconfig of the user, read-only or not, unless the guard becomes weaker. The sandbox binds a kubeconfig with no credentials read-only in its place.
- Code: `HostSandbox._resolve_repo_mounts` binds the tree of the request read-only with no `_checked_bind`. `run_popeye_scan` gave the working directory of the command as the tree. So a run from the home directory would show the home directory to Popeye.
- Command output, on this host: `pasta`, `slirp4netns` and `landrun` are not installed. `socat` 1.8.1.3, `kubectl` v1.37.1, `setpriv` of util-linux (with `--pdeathsig`) and Popeye 0.22.1 are installed. The devcontainer image (`.devcontainer/Dockerfile`) installs `bubblewrap` but not `socat`.
- Command output, a probe on this host: a shell started `kubectl proxy --unix-socket=<dir>/kube-api.sock` outside the sandbox, with `--reject-methods='^(POST|PUT|PATCH|DELETE)$'`. bubblewrap ran with `--unshare-all`, a tmpfs at `/tmp` and `--ro-bind <dir> <dir>`. In it, `socat TCP-LISTEN:8001,bind=127.0.0.1,fork,reuseaddr UNIX-CONNECT:<dir>/kube-api.sock` listened, and Popeye read a JSON kubeconfig whose only cluster was `http://127.0.0.1:8001`, with an empty user. Popeye ran under `prlimit --cpu=600 --as=2147483648` and gave the same 19 linters as a direct run with the kubeconfig of the user, the score 79, which a direct run also gives, and the exit code 1 for its issues. In the same sandbox, `socat` to `192.0.2.1:443` failed with `Network is unreachable`, and a POST through the relay got `403 Forbidden`.
- Command output, with the code of this change on this host: `SandboxToolExecutor` ran Popeye 0.22.1 with the profile, and the record named the network `kube-api`. The report had 19 linters. Through the same relay, `GET /version` got 200, a POST of a SelfSubjectAccessReview got 403 from the proxy, and a GET of the exec path of a pod got 403. A TCP connection from the sandbox to `192.0.2.1:443` failed (curl exit code 7). The scratch directory did not stay after the run. `devops k8s audit` ran Popeye through the relay, showed its findings and exited 0.
- Command output: six direct runs of Popeye 0.22.1 on the same cluster gave the score 78 three times and 79 three times: some runs scanned no NetworkPolicy, and the others scanned five. A run through the relay gives one of the same two reports, and the log of the proxy (`-v=6`) shows that it accepted every request of Popeye. So a difference of the score between a run through the relay and a direct run comes from Popeye, not from the relay.
- Limits of the mechanism (design.md, decision 1): the sandbox reaches each API path of the context that the RBAC of the user allows to read, less the paths that the proxy refuses. The path filter of `kubectl proxy` is a deny list, which it applies to the decoded and cleaned path: a new subresource that reaches past the API server passes until `CONST_KUBE_API_REJECTED_PATHS` lists it. Popeye reads each response, such as a Secret that the user can read, as in a direct run.
- Command output: with only `/usr` and the links of the sandbox policy, Popeye 0.22.1 stopped at start with `user: Current requires cgo or $USER set in environment`. With `/etc/passwd` bound read-only, it ran in full.
- Command output: Popeye with no `-n` scanned only the namespace of the context, and `-A` scanned every namespace. #2436 gives Popeye `-A` when a scan names no namespace, so every command of a scan names its scope, and the kubeconfig of the sandbox needs no namespace.
- Command output, kubectl v1.37.1: `kubectl config view --minify --output=json` gives the current context with its `namespace`, and `--context=<name>` gives that context. The credential values are `DATA+OMITTED` or `REDACTED`. A context that the kubeconfig does not have exits 1 with `error: cannot locate context <name>`, and a missing kubeconfig, or one with no current context, exits 1 with `error: current-context must exist in order to minify`.
- Code: the kubernetes client (`list_kube_config_contexts`) has no type information, so its import in a new module needs a `type: ignore`. `tests/test_architectural_invariants.py` holds `src type: ignore` at its ceiling, 51, and the new module makes 52. The change reads the kubeconfig with kubectl and raises no ceiling.
- Command output: a Python `subprocess.run(..., timeout=3)` of the host script, with `sleep 60` in bubblewrap, returned after 3.0 s, and no `kubectl proxy`, bubblewrap or `sleep` process stayed. With the code of this change, `run_subprocess(..., timeout=3)` of the same command timed out after 3.0 s, and no process of the run stayed. `subprocess.run` kills only the shell. bubblewrap ends with its parent through `--die-with-parent`, and `setpriv --pdeathsig KILL` gives `kubectl proxy` the same end, so the pipes close.

## Existing Tool Considered

- `kubectl proxy`, of the Kubernetes project, gives a client the API server of one context with the credentials of the kubeconfig, and filters methods and paths (`--reject-methods`, `--reject-paths`). It listens on a Unix socket with `--unix-socket`.
- `socat` relays the loopback port in the sandbox to that socket, and waits for a listener with `retry` and `interval`. bubblewrap gives the sandbox no network. `setpriv --pdeathsig` of util-linux ends the proxy with its parent. `kubectl config view --minify` reads the name of the context.
- The change builds no proxy, relay, filter or kubeconfig parser of its own. Its own code is two short shell scripts that connect these programs, and the kubeconfig of the sandbox.
- Internal code that the change deletes: the `DirectToolExecutor` default of Popeye, the `workdir` and `save_output` parameters of `run_popeye_scan`, the workspace check of `scan_popeye`, and the pass that `devops k8s audit` printed for a scan that did not run.
