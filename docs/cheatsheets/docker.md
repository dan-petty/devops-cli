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
