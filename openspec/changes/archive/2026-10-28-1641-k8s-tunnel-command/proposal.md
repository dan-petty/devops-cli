# Proposal

## Why

Issue #1641: off the home network, the tunnel kubeconfig context of #1595 works only while `cloudflared access tcp` runs in a terminal that someone keeps open. When the listener stops, `kubectl` fails with "connection refused" on the local port, and nothing says that the forward is missing. A second listener on the same port fails with "address already in use", so the user starts and stops the forward by hand. `k8s/README.md` gives the forward and the context as manual steps.

## What Changes

- A new command group, `devops k8s tunnel`:
  - `start` reads the hostname from the new setting `k8s.tunnel_host` and fails with an error that names the setting when it is unset. It runs `cloudflared access login --quiet https://<host>` in the foreground, so cloudflared shows its own Access login URL (or opens a browser) and stores the token without printing it. Then it starts `cloudflared access tcp --hostname <host> --url <address>:<port> --logfile <file>` detached in its own session, records the process under the data directory, and waits until the port accepts connections. When a recorded forward runs, it reports that forward and starts no other. With `--context`, it adds or updates the `<cluster>-tunnel` cluster and context with the `kubectl config` commands that `k8s/README.md` gave. `--dry-run` prints the commands and starts nothing.
  - `stop` signals the forward's process group with `terminate_process_group`, which refuses pid 0, pid 1 and the caller's own group, and removes the record. `--dry-run` names the process and signals nothing.
  - `status` reports the recorded forward, whether the port accepts connections, and, for the tunnel context, whether the API server answers. Any HTTP status from `/version`, also 401 or 403, counts as an answer, because the request reached the API server through the tunnel.
- The port defaults to `DEFAULT_K8S_TUNNEL_PORT` (16443) and `--port` sets another.
- `KubernetesService.api_server_answers` asks the API server of a context for `/version` and tells an HTTP answer apart from a connection failure.
- `k8s/port_forward_daemon.py` gives its state-file lock and its pid-and-start-time liveness check as functions, and the tunnel record uses both.
- `k8s/README.md` gives `devops k8s tunnel start --context` in place of the manual `cloudflared` and `kubectl config` steps.
- A command and a setting change what a user sees, so the change carries a spec delta: the new capability `k8s-api-tunnel`.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `k8s-api-tunnel`: the local end of the Kubernetes API route at `k8s.<domain>`, started, reported and stopped by `devops k8s tunnel`.

## Impact

- `src/devops_cli/k8s/tunnel.py` (new), `src/devops_cli/commands/k8s/tunnel.py` (new), `src/devops_cli/commands/k8s/__init__.py`.
- `src/devops_cli/core/process.py`: the process runner gains `spawn_detached`, which starts a child in a session of its own; `tests/support/fakes/process.py` records such a call and answers with a process that the test gives.
- `src/devops_cli/k8s/port_forward_daemon.py`, `src/devops_cli/k8s/service.py`, `src/devops_cli/k8s/api.py` (`api_error_type`).
- `src/devops_cli/config/settings.py` (`k8s.tunnel_host`), `src/devops_cli/config/defaults.py`, `src/devops_cli/exceptions/k8s.py`, `src/devops_cli/lang/en/`.
- `tests/k8s/test_k8s_tunnel.py` (new), the snapshot of the settings' variables (`tests/test_config_declarations.py`), the MCP exclusions (`tests/test_mcp.py`: the three commands start a background process or an interactive login, as `port-forward` does), and `tests/test_process.py`.
- `docs/TESTING.md`: how a test fakes a detached child.
- `k8s/README.md`, and the documentation that `devops docs generate --sync-readme` writes.

## Feasibility

- `cloudflared` 2026.10.4, the pinned version on this workstation: `cloudflared access login --help` gives `--quiet` ("do not print the jwt to the command line") and says that the command launches a browser or, on a headless system, prints a URL, then stores the token in local storage. `cloudflared access tcp --help` gives `--hostname`, `--url` ("the host:port to forward data to Cloudflare edge") and `--logfile`. Neither command runs itself in the background.
- The evidence in #1641 (2026-10-17): with the listener running, `kubectl --context <cluster>-tunnel get nodes` listed the nodes through `k8s.<domain>`. A second after it exited, the same command failed with "connection to the server 127.0.0.1:16443 was refused".
- On origin/main 0702d133, no `devops k8s tunnel` command exists. `devops k8s port-forward` already starts detached forwards with `start_new_session=True`, records them under the data directory with a locked state file and the pid's start time, and stops them with `terminate_process_group`.
- `KubernetesService.is_cluster_reachable` counts any exception, a 401 too, as not reachable, so it cannot tell a tunnel that reached the API server with a refused credential from a tunnel that is down.
- The test floor refuses every program except git, bwrap and kubectl's offline renderers. The tests therefore give `start` its own spawn function and start `git cat-file --batch`, which waits on its standard input, in place of cloudflared. A socket that the test binds stands in for cloudflared's listener.

## Existing Tool Considered

`cloudflared access tcp` does the forwarding and `cloudflared access login` does the Access login; the change builds neither. No tool keeps a `cloudflared access tcp` listener running: cloudflared has no daemon mode for it (`cloudflared service install` runs a tunnel connector, not an Access client), and a systemd user unit is not there in the devcontainer or on macOS. `devops k8s port-forward` already supervises detached forwards, so the tunnel uses its lock, its liveness check and `terminate_process_group`, and adds only the record of one forward. The change deletes the manual steps in `k8s/README.md`.
