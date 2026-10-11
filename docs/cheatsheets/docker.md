# Docker & Containers Tool Cheatsheet

Compare native `docker` and `docker compose` commands with `devops-cli` container diagnostics and resource monitoring.

---

## 1. Container Diagnostics & Metrics

| Action / Goal | Original Command (`docker`) | `devops-cli` Command | Key Enhancements in `devops-cli` |
| :--- | :--- | :--- | :--- |
| **Inspect Running Containers** | `docker ps -a` | `devops docker ps` | Compact formatted table detailing container ID, image, status, health status, and mapped host ports. |
| **Live Container Resource Stats** | `docker stats --no-stream` | `devops docker stats` | Structured memory percentage, CPU load, and network I/O stats with warning thresholds for high memory consumers (e.g. LLM nodes). |
| **Container Log Inspection** | `docker logs -f --tail 100 <container>` | `devops docker logs <container> [--tail <N>]` | Auto-detects container name prefix and strips ANSI escape sequences for log analysis. |

---

## 2. Image Build & Compose Orchestration

| Action / Goal | Original Command (`docker` / `docker compose`) | `devops-cli` Command | Key Enhancements in `devops-cli` |
| :--- | :--- | :--- | :--- |
| **Build Project Image** | `docker build -t devops-cli:latest .` | `devops docker build [--tag <tag>]` | Auto-detects `Dockerfile` context, passes proxy settings, and checks image layer size. |
| **Start Compose Stack** | `docker compose -f docker-compose.yml up -d` | `devops docker compose-up` | Validates host port availability before launch and checks service health. |
| **Stop Compose Stack** | `docker compose -f docker-compose.yml down` | `devops docker compose-down` | Gracefully terminates containers, removes orphan networks, and preserves volumes. |
| **Prune Unused Images & Volumes**| `docker system prune -af --volumes` | `devops docker prune` | Interactive confirmation gate with disk reclaim calculation before deleting dangling images and cache. |

---

## 3. Engine Socket Resolution & Podman Support

`devops-cli` negotiates Docker and Podman daemon endpoints automatically using the following precedence order:

1. **`CONTAINER_HOST`**: Standard container endpoint (honors Docker TLS environment variables `DOCKER_TLS_VERIFY` and `DOCKER_CERT_PATH`).
   > *Note*: If `CONTAINER_CONNECTION` is detected, `devops-cli` halts with an informative error directing configuration to `CONTAINER_HOST`.
2. **`DOCKER_HOST`**: Traditional Docker daemon environment override.
3. **`DOCKER_CONTEXT`**: Explicit context name from the environment.
4. **Current Context**: Non-default `currentContext` in `~/.docker/config.json`.
5. **Rootless Podman Socket**: `$XDG_RUNTIME_DIR/podman/podman.sock` (or `/run/user/<uid>/podman/podman.sock` when `XDG_RUNTIME_DIR` is unset), if the socket exists.
6. **Rootful Podman Socket**: `/run/podman/podman.sock`, if the socket exists and the current process has read/write permissions.
7. **Docker Default Socket**: Fallback to `/var/run/docker.sock`.

### Enabling Rootless Podman Socket

If the Docker default socket is unreachable, enable and start Podman's user socket:

```bash
systemctl --user enable --now podman.socket
```

Alternatively, set `CONTAINER_HOST` or `DOCKER_HOST` to point directly to your container socket:

```bash
export CONTAINER_HOST="unix://$XDG_RUNTIME_DIR/podman/podman.sock"
```

### Out-of-Scope Limits & Engine Differences

- **BuildKit Cache**: Podman does not maintain a separate BuildKit cache; its build layers are stored directly as images. `devops docker cache` informs the user and exits 1 on Podman engines; use `devops docker prune` to reclaim dangling image layers.
- **SSH Daemon Endpoints**: Remote `ssh://` endpoints are unsupported without SSH tunneling or optional dependencies.
- **Native Podman APIs**: Only the Docker-compatible Engine API endpoint of Podman is addressed; proprietary libpod-specific endpoints are not used.
- **Rootless Sandbox Permissions**: Rootless Podman engines run container processes as UID 0 inside the user namespace (mapped to the host user). Workload sandboxes automatically configure `user="0:0"` on rootless engines so sandboxed workloads can write to mounted workspace directories.
