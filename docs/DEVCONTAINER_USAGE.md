# Using the Published DevOps CLI Dev Container

`devops-cli` publishes pre-built, production-ready Dev Container images to the GitHub Container Registry (**GHCR**) on every release. You can use these published images directly in downstream repositories, GitHub Codespaces, and workstation environments without having to build the container or compile dependencies locally.

---

## 1. Published Container Images & Tags

The official `linux/amd64` image is hosted on GHCR at:
`ghcr.io/dan-petty/devops-cli/devcontainer`

| Tag Pattern | Example | Description | Best For |
| :--- | :--- | :--- | :--- |
| `latest` | `ghcr.io/dan-petty/devops-cli/devcontainer:latest` | Latest official stable release | Default development environments |
| `vX.Y.Z` | `ghcr.io/dan-petty/devops-cli/devcontainer:v0.2.16` | Immutable, pinned version | CI pipelines & reproducible environments |
| `sha256:...` | `ghcr.io/dan-petty/devops-cli/devcontainer@sha256:...` | Cryptographic digest pinning | Zero-trust compliance & air-gapped builds |

### Pulling the Image Directly
```bash
# Pull the latest published image
docker pull ghcr.io/dan-petty/devops-cli/devcontainer:latest

# Or pull a specific pinned release
docker pull ghcr.io/dan-petty/devops-cli/devcontainer:v0.2.16
```

---

## 2. Pre-Installed Tooling & Capabilities

The published Dev Container image is built on `debian:sid` (Debian Unstable) providing Python 3.14+ and includes comprehensive cloud-native, DevOps, and AI developer tooling pre-configured out of the box:

- **Runtimes & Package Managers**: Python 3.14+, `uv` (ultra-fast package & virtualenv manager), `git`, `zsh` with Oh My Zsh.
- **Containers & Virtualization**: Docker-in-Docker (DinD) enabled with rootless socket mapping for non-root user `vscode`.
- **Kubernetes & Cloud Native**: `kubectl`, `helm`, `minikube` (with optional GPU passthrough support), `kustomize`.
- **Infrastructure as Code**: `devops tf` wraps OpenTofu or Terraform; install `tofu` or `terraform` yourself, since the image ships neither.
- **Security & Compliance Integrations**: runners for `bandit`, `checkov`, `trivy`, `semgrep`, `gitleaks`, `kube-linter`, `pluto` and `actionlint` (`devops scan`, `devops ci`). Post-create installs every tool in `tools.lock` at its locked version (`devops install-tools`), including `semgrep`, `gitleaks`, `osv-scanner`, `bandit`, `trivy`, `kube-linter` and `pluto`. Install `checkov` and `actionlint` yourself, or add them to your project's dev dependencies.
- **Sandbox Confinement & Host Isolation**: Linux bubblewrap (`bwrap`) pre-installed for unprivileged namespace confinement of executable verification criteria and untrusted code execution. Criteria run the reviewed repository's own `.venv/bin` first on `PATH`, so `python` and `ruff` are the project's; run `uv sync` in that repository before a review, or criteria fall back to the system's `/usr/bin` tools.
- **AI Code Review & MCP Integration**: `devops-cli` suite pre-installed with Model Context Protocol (FastMCP) server endpoints (`devops mcp serve`), OpenTelemetry instrumentation, and Logfire.

---

## 3. Quickstart: Adding to Your Project

### Option A: Using the CLI (Recommended)

You can scaffold a complete, best-practice `.devcontainer/` setup targeting the published image using `devops devcontainer init`:

```bash
# Initialize a new project with the published GHCR container image
devops devcontainer init --name my-project --published

# --image currently writes :latest for devops-cli images; pin by editing "image" in the generated .devcontainer/devcontainer.json
devops devcontainer init --name my-project --image ghcr.io/dan-petty/devops-cli/devcontainer:v0.2.16
```

This scaffolds:
1. `.devcontainer/devcontainer.json`: Pre-configured manifest using the published image with `/tmp`, persistent user home volume, SSH directory forwarding, post-create lifecycle commands (`devops devcontainer post-create`), and IDE extensions.
2. `.vscode/mcp.json`: Model Context Protocol configuration exposing `devops-cli` tools to AI coding assistants (Claude Desktop, Cursor, VS Code, Antigravity IDE).
3. `AGENTS.md`, `CLAUDE.md` and `.github/copilot-instructions.md`: Operational engineering instructions and architectural constraints for AI pair programmers.
4. `.mcp.json`: the same MCP server for Claude Code.

---

### Option B: Manual `.devcontainer/devcontainer.json` Configuration

For existing repositories or custom setups, create `.devcontainer/devcontainer.json` adhering to modern performance and security best practices:

```json
{
  "name": "my-project-devops",
  "image": "ghcr.io/dan-petty/devops-cli/devcontainer:latest",
  "mounts": [
    "source=my-project-tmp,target=/tmp,type=volume",
    "source=my-project-data,target=${containerWorkspaceFolder}/.data,type=volume",
    "source=my-project-venv,target=${containerWorkspaceFolder}/.venv,type=volume",
    "source=my-project-uv,target=${containerWorkspaceFolder}/.uv,type=volume",
    "source=my-project-ruff-cache,target=${containerWorkspaceFolder}/.ruff_cache,type=volume",
    "source=my-project-home,target=/home/vscode,type=volume",
    "source=${localEnv:HOME}${localEnv:USERPROFILE}/.ssh,target=/home/vscode/.ssh,type=bind,consistency=cached"
  ],
  "containerEnv": {
    "DEVOPS_CLI_CONFIG": "${containerWorkspaceFolder}/config.yaml",
    "UV_MALWARE_CHECK": "1",
    "UV_CACHE_DIR": "${containerWorkspaceFolder}/.uv"
  },
  "postCreateCommand": "uv sync",
  "postStartCommand": "uv run pre-commit install",
  "customizations": {
    "vscode": {
      "extensions": [
        "ms-python.python",
        "ms-python.vscode-pylance",
        "charliermarsh.ruff",
        "tamasfe.even-better-toml",
        "ms-azuretools.vscode-docker",
        "ms-azuretools.vscode-containers",
        "ms-kubernetes-tools.vscode-kubernetes-tools"
      ],
      "settings": {
        "editor.formatOnSave": true,
        "editor.defaultFormatter": "charliermarsh.ruff",
        "editor.tabSize": 2,
        "editor.insertSpaces": true,
        "editor.rulers": [
          100
        ],
        "files.eol": "\n",
        "files.trimTrailingWhitespace": true,
        "files.insertFinalNewline": true,
        "terminal.integrated.defaultProfile.linux": "zsh",
        "python.defaultInterpreterPath": "${containerWorkspaceFolder}/.venv/bin/python",
        "python.terminal.activateEnvironment": true,
        "[python]": {
          "editor.defaultFormatter": "charliermarsh.ruff"
        }
      }
    },
    "antigravity": {
      "extensions": [
        "ms-python.python",
        "ms-python.vscode-pylance",
        "charliermarsh.ruff",
        "tamasfe.even-better-toml",
        "ms-azuretools.vscode-docker",
        "ms-azuretools.vscode-containers",
        "ms-kubernetes-tools.vscode-kubernetes-tools"
      ],
      "settings": {
        "editor.formatOnSave": true,
        "editor.defaultFormatter": "charliermarsh.ruff",
        "editor.tabSize": 2,
        "editor.insertSpaces": true,
        "editor.rulers": [
          100
        ],
        "files.eol": "\n",
        "files.trimTrailingWhitespace": true,
        "files.insertFinalNewline": true,
        "terminal.integrated.defaultProfile.linux": "zsh",
        "python.defaultInterpreterPath": "${containerWorkspaceFolder}/.venv/bin/python",
        "python.terminal.activateEnvironment": true,
        "[python]": {
          "editor.defaultFormatter": "charliermarsh.ruff"
        }
      }
    }
  },
  "remoteUser": "vscode"
}
```

> [!TIP]
> **Optional GPU Acceleration (NVIDIA Hosts)**: If running on a host with an NVIDIA GPU and `nvidia-container-toolkit` installed, pass GPUs to the container by adding:
> ```json
> "runArgs": ["--gpus", "all"]
> ```

---

## 4. Opening in Your Development Environment

### In VS Code or Cursor
1. Ensure the **Dev Containers** extension (`ms-vscode-remote.remote-containers`) is installed.
2. Open the command palette (`Ctrl+Shift+P` / `Cmd+Shift+P`).
3. Select **Dev Containers: Reopen in Container**.
4. VS Code pulls `ghcr.io/dan-petty/devops-cli/devcontainer:latest` (or your pinned tag) and mounts your workspace in seconds.

### In Antigravity IDE
Antigravity IDE automatically discovers `.devcontainer/devcontainer.json` at the workspace root, provisions the container environment, maps configured FastMCP endpoints, and initializes local tool integrations.

### In GitHub Codespaces
When creating a Codespace from your repository, GitHub automatically detects `.devcontainer/devcontainer.json` and provisions the cloud environment using the pre-built GHCR image.

---

## 5. Customizing & Extending the Image

If your project requires additional system packages, custom C extensions, or proprietary CLI utilities, extend the published base image via a multi-stage or layered `.devcontainer/Dockerfile`:

### `.devcontainer/Dockerfile`
```dockerfile
FROM ghcr.io/dan-petty/devops-cli/devcontainer:v0.2.16

# Switch to root to install system packages with apt-get cleanup
USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    valkey-tools \
    && rm -rf /var/lib/apt/lists/*

# Always return to non-root developer user
USER vscode
```

### Corresponding `.devcontainer/devcontainer.json`
```json
{
  "name": "my-extended-project",
  "build": {
    "dockerfile": "Dockerfile",
    "context": ".."
  },
  "mounts": [
    "source=my-project-tmp,target=/tmp,type=volume",
    "source=my-project-venv,target=${containerWorkspaceFolder}/.venv,type=volume",
    "source=my-project-home,target=/home/vscode,type=volume",
    "source=${localEnv:HOME}${localEnv:USERPROFILE}/.ssh,target=/home/vscode/.ssh,type=bind,consistency=cached"
  ],
  "containerEnv": {
    "DEVOPS_CLI_CONFIG": "${containerWorkspaceFolder}/config.yaml"
  },
  "postCreateCommand": "uv sync",
  "customizations": {
    "vscode": {
      "settings": {
        "python.defaultInterpreterPath": "${containerWorkspaceFolder}/.venv/bin/python"
      }
    }
  },
  "remoteUser": "vscode"
}
```

> [!TIP]
> **Keep Python Dependencies in `pyproject.toml`**: Avoid `pip install` commands in your `Dockerfile`. Manage all Python dependencies declaratively via `pyproject.toml` and let `postCreateCommand: "uv sync"` install them into the named `.venv` volume. This keeps image rebuilds fast and dependencies reproducible across teammates.

---

## 6. Configuring AI Reviewers & Model Context Protocol (MCP)

Inside the Dev Container, `devops-cli` is accessible globally. You can configure AI reviewers and FastMCP servers for automated agentic pairing:

### Configuring AI Credentials Securely
```bash
# Supply API key via environment variable (or secret manager / OS Keyring) to avoid plaintext secrets in shell history
export ANTHROPIC_API_KEY="sk-ant-..."  # or export DEVOPS_CLI_AI_API_KEY="sk-ant-..."

# Configure Anthropic Claude provider
devops ai config --provider claude

# Or configure local Ollama running on your workstation host
# Note: For Linux hosts without Docker Desktop, add "runArgs": ["--add-host=host.docker.internal:host-gateway"] to devcontainer.json
# and allow local/private network egress:
export DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK=true
devops ai config --provider ollama --model qwen2.5-coder:7b --ollama-urls http://host.docker.internal:11434

# Verify provider connectivity and latency
devops ai test

# Run every reviewer persona on the active branch against main
devops review branch --all

# Or explicitly review a specific feature branch against main
devops review branch feat/my-feature --base main

# Run targeted security review on a specific directory
devops review path src/ --persona devsecops
```

### Exposing FastMCP Tools to AI Assistants (`.vscode/mcp.json`)
To connect external IDE tools (Cursor, Claude Desktop, Antigravity IDE, VS Code) to the container's FastMCP server:

```json
{
  "mcpServers": {
    "devops-cli": {
      "command": "uv",
      "args": [
        "run",
        "--with",
        "fastmcp",
        "devops",
        "mcp",
        "serve",
        "--transport",
        "stdio"
      ],
      "env": {
        "PATH": "${workspaceFolder}/.venv/bin:${env:HOME}/.local/bin:/usr/local/bin:/usr/bin:/bin"
      },
      "cwd": "${workspaceFolder}"
    }
  }
}
```

---

## 7. Performance & Security Best Practices

### Named Docker Volumes vs. Host Bind Mounts
On Windows (WSL2 9P filesystem) and macOS (VirtioFS), bind-mounting directories with thousands of small files (like `.venv`, `.uv`, or `.ruff_cache`) incurs significant filesystem translation overhead.
- **Best Practice**: Mount named Docker volumes for high-churn paths (`.venv`, `.data`, `.uv`, `/tmp`, and `/home/vscode`).
- **Result**: Native Linux ext4 performance inside the container, reducing `uv sync` and test execution times by up to **10x**.

### SSH Key Management & Host Agent Forwarding
- **SSH Agent Forwarding (Recommended / Zero-Key Exposure)**: In VS Code and Dev Containers, the host SSH agent is automatically forwarded into the container when `SSH_AUTH_SOCK` is active on the host, allowing seamless git operations without copying or mounting private keys into the container.
- **Direct `.ssh` Directory Bind Mount (Local Development Convenience)**: If host agent forwarding is unavailable, bind-mounting the host `.ssh` directory allows authentication across Windows, macOS, and Linux:
```json
"source=${localEnv:HOME}${localEnv:USERPROFILE}/.ssh,target=/home/vscode/.ssh,type=bind,consistency=cached"
```
> [!WARNING]
> Bind-mounting the entire host `.ssh` directory exposes your private keys to processes running inside the container. In shared or zero-trust environments, prefer SSH Agent forwarding or dedicate a container-specific key pair (`~/.ssh/id_ed25519_devcontainer`).

### Keyring for `gh`, git and `devops` Secrets
Containers scaffolded by `devops devcontainer init` run Debian's `gnome-keyring` as their Secret Service. Without it, `gh auth login` saves its token to `~/.config/gh/hosts.yml` in plain text, and `devops` has nowhere to store secrets.
- **Where it runs**: `containerEnv` sets `DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus`, and `devops devcontainer post-start` starts that session bus. gnome-keyring then starts on the first secret request. The bus lives under `/run`, which is private to each container, not on the shared `/tmp` volume.
- **Other images**: the published image ships gnome-keyring. On any other image, `devops devcontainer post-create` installs `gnome-keyring` and `dbus-x11` with apt.
- **Unlocking**: the keyring starts locked every time a container starts, and the container asks for the password on its own:
  1. `devops devcontainer post-start` prompts in the terminal VS Code shows while the container starts.
  2. If nobody answers within 60 seconds, the first interactive terminal you open asks instead. Only one terminal asks at a time, and none do once the keyring is unlocked.

  The first time, you choose the password, so it is asked for twice. Empty passwords are refused, because they would store every secret in plain text. Once the keyring is unlocked, any plaintext `gh` token is moved into it automatically. You can also unlock by hand at any time:
  ```bash
  devops devcontainer unlock-keyring
  ```
- **Moving an existing token in by hand**: if the automatic move is skipped (for example because `GH_TOKEN` is set), move a plaintext `gh` token into the keyring without minting a new one:
  ```bash
  gh auth token -h github.com | gh auth login -h github.com --with-token
  ```
  `devops devcontainer post-start` and `unlock-keyring` both warn about any host that still has a plaintext token, and print this command for it.
- **Git over HTTPS**: `containerEnv` routes `github.com` and `gist.github.com` credentials through `gh auth git-credential`, so git uses the same keyring-backed token as `gh`. These `GIT_CONFIG_*` entries are read after every config file, so they override the helper VS Code adds to forward credentials from the host. While the keyring is locked, `git fetch` over HTTPS fails instead of quietly using the host's credentials. Other hosts are unchanged.
- **`devops` secrets**: `devops config` refuses to store a secret while the keyring is locked, and names `unlock-keyring` in the error. `devops k8s push-secrets`, and the `deploy-stack` that the post-start auto-deploy (`DEVOPS_K8S_AUTO_DEPLOY`) runs, stop before applying anything while it is locked; unlock it, then run `devops k8s deploy-stack --stack <stack>` again. It also refuses keyring setups that could fall back to a plaintext backend.

> [!WARNING]
> `gh` still falls back to a plaintext `hosts.yml` token if you log in while the keyring is locked (cli/cli#10108). Unlock first. post-start flags the fallback on the next container start.

### Zero-Root Principle
The published Dev Container executes by default as non-root user `vscode` (UID 1000, GID 1000) with passwordless `sudo` privileges if required. Always ensure custom scripts and daily development commands execute under `vscode` to prevent permission collisions on host-mounted files.

---

## 8. Kubernetes Cluster Topologies & Configuration

The DevOps CLI Dev Container provides first-class support for both container-embedded local Kubernetes clusters and external workstation or cloud-managed clusters.

```mermaid
graph TD
    A[DevContainer Workspace] --> B{k8s.context Setting}
    B -->|minikube (default)| C[Embedded Minikube Cluster]
    B -->|docker-desktop| D[Docker Desktop K8s on Host]
    B -->|kind / k3s / k3d| E[Local Host Cluster]
    B -->|EKS / GKE / AKS| F[Cloud-Managed Cluster]
    C -->|Docker-in-Docker Driver| G[Pods: Monitoring, ArgoCD, Jaeger, LLMs]
    D -->|~/.kube bind mount| H[Host Docker Desktop Runtime]
    E -->|host.docker.internal| I[Host Container Runtime]
    F -->|Cloud CLI / IAM Auth| J[Remote Cloud Infrastructure]
```

### Configuration Setting: `k8s.context`

The active Kubernetes cluster target is governed by the configuration option `k8s.context` in `config.yaml`, with environment variable override `DEVOPS_CLI_K8S_CONTEXT`:

```bash
# View active Kubernetes context
devops config show | grep k8s.context

# Set active context to embedded Minikube
devops config set k8s.context minikube

# Set active context to Docker Desktop
devops config set k8s.context docker-desktop

# Set active context to a local kind cluster
devops config set k8s.context kind-dev-cluster

# Set active context to a cloud-managed cluster
devops config set k8s.context arn:aws:eks:us-west-2:123456789012:cluster/staging-cluster
```

---

### Topology 1: Embedded Minikube in DevContainer (Default Mode)

When developing in self-contained environments or GitHub Codespaces, the Dev Container runs an embedded single-node Minikube cluster using the Docker-in-Docker (`--driver=docker`) driver.

#### Conditional Autostart Behavior
- **Default Autostart**: If `k8s.context` is set to `minikube` (the default), `devops devcontainer post-start` automatically verifies and starts the Minikube cluster when the Dev Container opens.
- **Resource Protection**: If `k8s.context` is configured to any other cluster (e.g. `docker-desktop` or a cloud cluster), Minikube **will not start**, preserving workstation CPU, RAM, and disk space.
- **Environment Override**: The `DEVOPS_MINIKUBE_AUTOSTART` environment variable can explicitly force or disable autostart regardless of the configured context:
  - `DEVOPS_MINIKUBE_AUTOSTART=true`: Force Minikube to autostart even if `k8s.context` points elsewhere.
  - `DEVOPS_MINIKUBE_AUTOSTART=false`: Prevent Minikube from starting automatically under any circumstances.
- **Context-Switching Autostart**: If you switch to the `minikube` context via `devops k8s switch-context minikube`, DevOps CLI checks if Minikube is running and **automatically starts it** if it is stopped.

#### GPU Passthrough & CPU Fallback
On workstations equipped with NVIDIA GPUs, Minikube automatically attempts to start with hardware GPU passthrough (`--gpus all`):
```bash
minikube start --driver=docker --gpus=all   # only when nvidia-smi is present; otherwise minikube start --driver=docker
```
If the container runtime lacks NVIDIA Container Toolkit support or fails to allocate GPUs, DevOps CLI automatically detects the failure and transparently falls back to CPU mode, ensuring container startup never fails due to missing GPU drivers.

#### Add-Ons
devops-cli enables no Minikube add-ons; minikube's defaults (`default-storageclass`, `storage-provisioner`) apply. Enable others with `minikube addons enable ingress` (or `metrics-server`, `dashboard`).

---

### Topology 2: Docker Desktop Kubernetes (`docker-desktop`)

If you run Docker Desktop on macOS or Windows and have Kubernetes enabled in Docker Desktop settings, you can connect the Dev Container directly to your host cluster instead of running an embedded Minikube instance.

#### 1. Mount Host Kubeconfig into DevContainer
In `.devcontainer/devcontainer.json`, add a bind mount for your host `.kube` directory:

```json
"mounts": [
  "source=${localEnv:HOME}${localEnv:USERPROFILE}/.kube,target=/home/vscode/.kube,type=bind,consistency=cached"
]
```

#### 2. Configure Host Network Endpoint
In Docker Desktop, the API server endpoint in `~/.kube/config` often defaults to `https://127.0.0.1:6443` or `https://kubernetes.docker.internal:6443`. From inside the Dev Container, `127.0.0.1` refers to the container itself.
- Ensure the cluster server in `~/.kube/config` points to `https://host.docker.internal:6443`.
- On Linux hosts without Docker Desktop, ensure `host.docker.internal` is mapped via `devcontainer.json`:
  ```json
  "runArgs": ["--add-host=host.docker.internal:host-gateway"]
  ```

#### 3. Set Active Context
```bash
# Configure DevOps CLI to target Docker Desktop
devops config set k8s.context docker-desktop

# Switch active context and verify connectivity
devops k8s switch-context docker-desktop
devops k8s status
```

> [!TIP]
> **Zero Minikube Overhead**: With `k8s.context` set to `docker-desktop`, embedded Minikube remains completely stopped, saving up to 8 GB of RAM and multiple CPU cores on your host workstation.

---

### Topology 3: Local Workstation Clusters (`kind`, `k3s`, `k3d`)

For local multi-node cluster testing or lightweight k3s environments running directly on your host:

#### 1. Forward Kubeconfig
Ensure your host kubeconfig containing the `kind` or `k3d` context is mounted into `/home/vscode/.kube` (as shown in Topology 2).

#### 2. Adjust Localhost Endpoint
For `kind` clusters running in host Docker, the control plane container is exposed on a host port (e.g. `https://127.0.0.1:39485`). Update the cluster server address in kubeconfig from `127.0.0.1` to `host.docker.internal`:
```yaml
# In ~/.kube/config:
clusters:
- cluster:
    certificate-authority-data: ...
    server: https://host.docker.internal:39485
  name: kind-dev-cluster
```

#### 3. Set Context & Deploy Stacks
```bash
# Set context
devops config set k8s.context kind-dev-cluster
devops k8s switch-context kind-dev-cluster

# Verify cluster status
devops k8s status

# Deploy the infrastructure stack (Argo CD, monitoring, OpenTelemetry); with the keyring
# unlocked, it first writes the stack's Secrets from the keyring (`devops k8s push-secrets`)
devops k8s deploy-stack --stack infra
```

---

### Topology 4: Cloud-Managed Kubernetes (Amazon EKS, Google GKE, Azure AKS)

DevOps CLI in DevContainers can operate directly on remote cloud-managed Kubernetes clusters across staging, QA, and production environments.

#### Cloud CLI & Credential Forwarding
To authenticate against cloud Kubernetes clusters, forward the respective cloud CLI credential directories into the Dev Container:

| Cloud Provider | Host Credential Path | DevContainer Mount Target |
| :--- | :--- | :--- |
| **Amazon Web Services (EKS)** | `~/.aws` | `/home/vscode/.aws` |
| **Google Cloud Platform (GKE)** | `~/.config/gcloud` | `/home/vscode/.config/gcloud` |
| **Microsoft Azure (AKS)** | `~/.azure` | `/home/vscode/.azure` |

Add the appropriate bind mounts to your `.devcontainer/devcontainer.json`:
```json
"mounts": [
  "source=${localEnv:HOME}${localEnv:USERPROFILE}/.kube,target=/home/vscode/.kube,type=bind,consistency=cached",
  "source=${localEnv:HOME}${localEnv:USERPROFILE}/.aws,target=/home/vscode/.aws,type=bind,consistency=cached",
  "source=${localEnv:HOME}${localEnv:USERPROFILE}/.config/gcloud,target=/home/vscode/.config/gcloud,type=bind,consistency=cached",
  "source=${localEnv:HOME}${localEnv:USERPROFILE}/.azure,target=/home/vscode/.azure,type=bind,consistency=cached"
]
```

Alternatively, inject authentication tokens or access keys via container environment variables:
- AWS: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `AWS_REGION`
- GCP: `GOOGLE_APPLICATION_CREDENTIALS=/workspace/service-account.json`
- Azure: `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`

#### Generating Cluster Credentials

##### Amazon EKS
```bash
# Update kubeconfig with remote EKS cluster endpoint and IAM authentication
aws eks update-kubeconfig --name <cluster-name> --region <region>

# Configure DevOps CLI to use the EKS context
devops config set k8s.context arn:aws:eks:<region>:<account-id>:cluster/<cluster-name>
devops k8s switch-context arn:aws:eks:<region>:<account-id>:cluster/<cluster-name>
```

##### Google Kubernetes Engine (GKE)
```bash
# Fetch GKE cluster credentials
gcloud container clusters get-credentials <cluster-name> --region <region> --project <project-id>

# Configure DevOps CLI context
devops config set k8s.context gke_<project-id>_<region>_<cluster-name>
devops k8s switch-context gke_<project-id>_<region>_<cluster-name>
```

##### Azure Kubernetes Service (AKS)
```bash
# Fetch AKS cluster credentials
az aks get-credentials --resource-group <resource-group> --name <cluster-name>

# Configure DevOps CLI context
devops config set k8s.context <cluster-name>
devops k8s switch-context <cluster-name>
```

#### Private Endpoints & Egress Safety
When connecting to private cloud Kubernetes clusters (e.g. within an AWS VPC, GCP Private Service Connect, or Azure VNet):
- **VPN / Direct Connect**: Ensure your workstation host is connected to the appropriate corporate VPN or interconnect before launching the Dev Container.
- **Network Routing & Internal DNS**: Ensure your host network or container bridge routes traffic to private API server subnets. If using private DNS zones (e.g. Route 53 Private Hosted Zones, Cloud DNS, or Azure Private DNS), configure host/container DNS resolution (`/etc/resolv.conf`) so that `kubectl` can resolve private cluster endpoints.
- **Zero Information Leakage Compliance**: Never commit private IP addresses (RFC 1918), corporate internal hostnames, or cluster access tokens into `config.yaml` templates, manifests, or task tracking. Always use abstract placeholders (`<cluster-name>`, `<region>`, `arn:aws:eks:...`).

---

### Context Management & Operations Workflow

```bash
# 1. List all available kubeconfig contexts and identify active cluster
devops k8s contexts

# 2. Switch context (autostarts a stopped Minikube; also saves k8s.context)
devops k8s switch-context <context-name>

# 3. Probe cluster health, nodes, and component statuses
devops k8s status

# 4. View real-time pod health across all namespaces
devops k8s pods --all-namespaces

# 5. Deploy infrastructure and observability stacks to the active cluster
devops k8s deploy-stack --stack infra     # ArgoCD, k8s-monitoring (Alloy), Prometheus, Grafana, OTel Collector, Jaeger
devops k8s deploy-stack --stack llm       # Ollama profiles, LLM gateway, Open WebUI, Qdrant, Valkey
devops k8s deploy-stack --stack logging   # Loki, Fluent Bit
devops k8s deploy-stack --stack all       # all three

# 6. Stream logs from a deployed controller
devops k8s stream-logs argocd-server -n argocd --tail 100 -f
```
