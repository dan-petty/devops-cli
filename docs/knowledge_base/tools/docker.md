# Knowledge Base: Docker (Containerization & Runtime Engine)

## 1. Overview & Purpose

Docker provides OS-level virtualization to deliver software in lightweight, isolated packages known as containers. In the `devops-cli` ecosystem, Docker powers development containerization (DevContainers), Docker-in-Docker (DinD) workstation support, container image publishing to GitHub Container Registry (GHCR), Minikube container drivers, and container vulnerability scanning.

---

## 2. Usage Information & Architecture

- **DevContainer Base Architecture**: `devops-cli` provides an enterprise-ready base image (`ghcr.io/dan-petty/devops-cli/devcontainer:latest`) containing Python 3.14, Docker CLI, Kubernetes CLI tools, OpenTofu, and DevOps CLI binaries.
- **Docker-in-Docker (DinD)**: Enabled via volume mounting `/var/run/docker.sock` into the container, allowing devcontainers to build, run, and inspect container workloads on the host engine.
- **GPU Passthrough**: Development containers and Minikube clusters are configured with automatic NVIDIA GPU passthrough (`--gpus all`) when `nvidia-smi` is detected on the host.
- **CLI Subcommand**: `devops docker` provides stats, container status, image inspection, and cleanup operations.

---

## 3. Common & Advanced Commands

### DevOps CLI Docker Subcommands
```bash
# View active container resource utilization (CPU, memory, net, I/O)
devops docker stats

# Clean up dangling images, unused networks, and build cache
devops docker prune --all
```

### Standard & Advanced Docker Commands
```bash
# Build multi-stage container image locally
docker build -t ghcr.io/dan-petty/devops-cli/devcontainer:local -f .devcontainer/Dockerfile .

# Inspect running containers with formatted JSON output
docker ps --format "table {{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Ports}}"

# Execute interactive shell inside a running container
docker exec -it <container_id> /bin/zsh

# Inspect container network or volume mounts
docker inspect <container_id> | jq '.[0].Mounts'

# Tail container logs with timestamps
docker logs -f --tail 100 <container_id>
```

---

## 4. Best Practice Guidance

1. **Multi-Stage Builds**: Always utilize multi-stage Dockerfiles to separate build tools, compiler dependencies, and cache from lightweight final runtime images.
2. **Deterministic Base Images**: Base images must pin specific major/minor tags (e.g. `python:3.14-trixie`) rather than floating `latest` tags during production image assembly.
3. **Build Context Optimization**: Use `.dockerignore` to exclude `.git/`, `.venv/`, `__pycache__/`, `.data/`, and scratch logs from being transferred into the Docker build daemon context.
4. **Non-Root Execution**: Development environments default to standard developer user accounts (`vscode`) with sanitized sudo privileges rather than running applications as bare `root`.

---

## 5. Security Recommendations & Zero-Trust Policies

- **Never Hardcode Secrets**: Never bake API tokens, SSH private keys, or credentials into Dockerfiles or build arguments.
- **Socket Permissions**: When mounting `/var/run/docker.sock`, ensure container processes do not expose unauthenticated TCP ports to the external network.
- **Vulnerability Scanning**: Scan all base images and release tags with Trivy (`devops scan image <image_name>`) prior to pushing to GHCR.
- **PR Image Tagging Policy**: Pull request container builds must NEVER be tagged with `latest`. Only merges to `main` tag `latest`.

---

## 6. General Standards & Reference Guidelines

- **Registry Namespace**: Container images are hosted on GitHub Container Registry under `ghcr.io/dan-petty/devops-cli/devcontainer`.
- **Labels & OCI Annotations**: Include OpenContainer annotations (`org.opencontainers.image.source`, `org.opencontainers.image.description`, `org.opencontainers.image.version`) in all published manifests.
