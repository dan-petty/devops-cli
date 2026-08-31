# Code Library: Docker SDK (Container Daemon Controller)

## 1. Project References

| Resource | Endpoint / URL |
| :--- | :--- |
| **Official Documentation** | [docker-py.readthedocs.io](https://docker-py.readthedocs.io/) |
| **Public Git Repository** | [github.com/docker/docker-py](https://github.com/docker/docker-py) |
| **Official PyPI Package** | [pypi.org/project/docker](https://pypi.org/project/docker/) (`7.2.0`) |
| **DevOps CLI Integration** | [`src/devops_cli/commands/docker.py`](file:///workspaces/devops-cli/src/devops_cli/commands/docker.py) • [`src/devops_cli/docker/`](file:///workspaces/devops-cli/src/devops_cli/docker/) |

---

## 2. General Information & Architecture

The **Docker SDK for Python** (`docker-py`) allows programmatic management of the Docker Engine daemon over Unix domain sockets (`/var/run/docker.sock`), Windows named pipes, or TCP endpoints.

In `devops-cli`:
- **Workstation Health & Stats**: Powers `devops docker stats`, collecting real-time CPU percentages, memory usage, network I/O, and container health states.
- **Container Lifecycle**: Powers container start, stop, restart, image pulling, and volume inspections.
- **DevContainer Management**: Validates container runtime capabilities in developer workstations.

---

## 3. Comparable Projects & Tradeoffs

| Library | Strengths | Weaknesses | Why `devops-cli` Chose Docker SDK |
| :--- | :--- | :--- | :--- |
| **`docker` (Official SDK)** | Direct Unix socket communication, high-speed streaming stats, container event streams, zero subprocess overhead. | Requires Docker Engine or Podman socket running. | **Selected**: The official, most reliable Python SDK for local container management. |
| **`podman-py`** | Dedicated SDK for rootless Podman engines. | Smaller ecosystem, requires Podman service socket active. | Docker SDK connects seamlessly to Podman's Docker-compatible socket. |
| **`docker` CLI Subprocess** | Executes `docker ps`, `docker stats`. | High process spawn overhead, fragile parsing of tabular text output. | Rejected: Docker SDK provides structured native Python dicts. |

---

## 4. Key Concepts & Core Patterns

1. **`DockerClient` Initialization**:
   ```python
   import docker

   client = docker.from_env()
   ```
2. **Container Collections**:
   - `client.containers.list(all=True)`: Lists all active/stopped containers.
   - `client.containers.get("container_id_or_name")`: Fetches specific container.
3. **Real-Time Resource Metrics**: `container.stats(stream=False)` captures an instantaneous CPU/memory snapshot.
4. **Defensive Socket Error Handling**: Catches `docker.errors.DockerException` when the Docker daemon is stopped or socket permissions are restricted.

---

## 5. Common & Advanced Usage Examples

### Collecting Real-Time Container Resource Statistics
```python
import docker
from docker.errors import DockerException


def get_container_metrics() -> list[dict]:
    try:
        client = docker.from_env()
        containers = client.containers.list()
    except DockerException as exc:
        return [{"error": f"Docker daemon unreachable: {exc}"}]

    metrics = []
    for c in containers:
        stats = c.stats(stream=False)
        cpu_delta = (
            stats["cpu_stats"]["cpu_usage"]["total_usage"]
            - stats["precpu_stats"]["cpu_usage"]["total_usage"]
        )
        system_delta = (
            stats["cpu_stats"]["system_cpu_usage"] - stats["precpu_stats"]["system_cpu_usage"]
        )
        cpu_pct = (cpu_delta / system_delta) * 100.0 if system_delta > 0 else 0.0

        metrics.append(
            {
                "name": c.name,
                "status": c.status,
                "cpu_percent": round(cpu_pct, 2),
                "memory_mb": round(stats["memory_stats"].get("usage", 0) / (1024 * 1024), 2),
            }
        )
    return metrics
```

---

## 6. Best Practices & Security Standards

1. **Lazy SDK Loading**: Dynamically import `docker` only when Docker subcommands are invoked.
2. **Defensive Daemon Probing**: `docker.from_env()` should always be wrapped in a `try...except DockerException` block with clear instructions for starting the daemon.
3. **Close Client Sessions**: Explicitly call `client.close()` when long-running background tasks terminate.
