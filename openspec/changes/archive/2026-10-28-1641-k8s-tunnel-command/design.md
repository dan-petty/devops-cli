# Design

## Context

`cloudflared access tcp` runs in the foreground and does not detach. Its first connection needs an Access token; when it has none, it starts the login and prints the login URL to its own output, which a detached process does not show.

## Decisions

### Login first, in the foreground; then the forward, detached

`start` runs `cloudflared access login --quiet https://<host>` with the terminal attached. cloudflared shows the login URL or opens a browser, waits for the login, stores the token and, with `--quiet`, does not print it. With a stored token that is still valid, the command ends at once. The detached `access tcp` then finds the token, so no login prompt goes into its log.

Rejected: start the forward first and read the login URL from its log file. The URL appears only when a client connects, so `start` would have to connect, wait and match cloudflared's log text, which can change in any release.

### One record, with the port-forward daemon's lock and liveness check

The record is `k8s/tunnel.json` under the data directory: pid, process start time, hostname, address, port, log file and the tunnel context. `start` holds the lock of `port_forward_daemon` from its read of the record to its save, so two runs at once start one forward. A pid counts as the forward only while it has the start time recorded at launch.

Rejected: put the tunnel in the port-forward state file. `devops k8s port-forward stop` would then stop the tunnel too, and a port-forward record has a namespace and a service that a tunnel does not have.

### What "the API server answers" means

`status` calls `/version` through `KubernetesService` with the tunnel context. Any HTTP status counts as an answer: a 401 or a 403 tells that the tunnel reached the API server and the credential was refused. A connection error or a timeout counts as no answer.

### The tunnel context

`start --context` reads the cluster, the user and the CA data of a home context (`--from-context`, default `k8s.context`) with `kubectl config view --raw --minify --flatten`, which inlines a CA file, and writes the cluster and the context `<cluster>-tunnel` with `kubectl config set-cluster`, `set` and `set-context`. The server is `https://<address>:<port>` and the TLS server name is `kubernetes.default.svc`, as `k8s/README.md` gave them. `start` does not switch to the context: `devops k8s switch-context <cluster>-tunnel` does that.

### Configuration

`k8s.tunnel_host` holds the hostname, with no fallback; an unset setting stops `start` with an error that names it. The port is `DEFAULT_K8S_TUNNEL_PORT`, 16443, the port of `k8s/README.md`, and `--port` sets another. The listener binds `DEFAULT_REST_HOST`.
