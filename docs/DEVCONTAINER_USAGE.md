# Using the Published DevOps CLI Dev Container

`devops-cli` publishes pre-built, production-ready Dev Container images to the GitHub Container Registry (**GHCR**) on every release. You can use these published images directly in downstream repositories and workstation environments without having to build the container or compile dependencies locally.

---

## 1. Published Container Images & Tags

The official images are hosted on GHCR at:
`ghcr.io/dan-petty/devops-cli/devcontainer`

| Tag Pattern | Example | Description | Best For |
| :--- | :--- | :--- | :--- |
| `latest` | `ghcr.io/dan-petty/devops-cli/devcontainer:latest` | Latest official stable release | Default development environments |
| `vX.Y.Z` | `ghcr.io/dan-petty/devops-cli/devcontainer:v0.2.8` | Immutable, pinned version | CI pipelines & reproducible environments |

### Pulling the Image Directly
```bash
# Pull the latest published image
docker pull ghcr.io/dan-petty/devops-cli/devcontainer:latest

# Or pull a specific pinned release
docker pull ghcr.io/dan-petty/devops-cli/devcontainer:v0.2.8
```

---

## 2. What's Pre-Installed in the Container

The published Dev Container image is built on Python 3.14 (`trixie`) and includes all essential cloud-native and DevOps tooling pre-configured out of the box:

- **Runtimes & Package Managers**: Python 3.14+, `uv`, `git`, `zsh` with Oh My Zsh.
- **Containers & Virtualization**: Docker-in-Docker (DinD) enabled for non-root users.
- **Kubernetes & Cloud Native**: `kubectl`, `helm`, `minikube`, `kustomize`.
- **Infrastructure as Code**: OpenTofu (`tofu`) and Terraform (`terraform`) dual compatibility.
- **Security & Compliance Scanners**: Aqua `trivy`, Red Hat `kube-linter`, `popeye`, Fairwinds `pluto`, `bandit`, `actionlint`.
- **AI Code Review & MCP Integration**: `devops-cli` binaries pre-installed with Model Context Protocol (MCP) server endpoints.

---

## 3. Quickstart: Adding to Your Project

### Option A: Using the CLI (Recommended)

You can scaffold a `.devcontainer/` setup targeting the published image using `devops devcontainer init`:

```bash
# Initialize a new project with the published GHCR container image
devops devcontainer init --name my-project --published

# Or specify a custom pinned tag
devops devcontainer init --name my-project --image ghcr.io/dan-petty/devops-cli/devcontainer:v0.2.8
```

This creates:
1. `.devcontainer/devcontainer.json`: Pre-configured manifest using the published image.
2. `.vscode/mcp.json`: Model Context Protocol configuration exposing `devops-cli` tools to AI coding assistants (Claude Desktop, Cursor, VS Code, Antigravity IDE).

---

### Option B: Manual `.devcontainer/devcontainer.json` Configuration

Add a `.devcontainer/devcontainer.json` file to the root of your project:

```json
{
  "name": "my-project-devops",
  "image": "ghcr.io/dan-petty/devops-cli/devcontainer:latest",
  "mounts": [
    "source=${localEnv:HOME}/.ssh,target=/home/vscode/.ssh,type=bind,consistency=cached",
    "source=my-project-bashhistory,target=/commandhistory,type=volume"
  ],
  "postCreateCommand": "uv sync",
  "postStartCommand": "uv run pre-commit install",
  "customizations": {
    "vscode": {
      "extensions": [
        "ms-python.python",
        "charliermarsh.ruff",
        "ms-azuretools.vscode-docker",
        "ms-kubernetes-tools.vscode-kubernetes-tools",
        "tamasfe.even-better-toml"
      ],
      "settings": {
        "editor.formatOnSave": true,
        "files.trimTrailingWhitespace": true,
        "terminal.integrated.defaultProfile.linux": "zsh",
        "python.defaultInterpreterPath": "/usr/local/bin/python"
      }
    }
  },
  "remoteUser": "vscode"
}
```

---

## 4. Opening in Your Development Environment

### In VS Code or Cursor
1. Ensure the **Dev Containers** extension (`ms-vscode-remote.remote-containers`) is installed.
2. Open the command palette (`Ctrl+Shift+P` / `Cmd+Shift+P`).
3. Select **Dev Containers: Reopen in Container**.
4. VS Code will pull `ghcr.io/dan-petty/devops-cli/devcontainer:latest` and mount your workspace in seconds.

### In GitHub Codespaces
When creating a Codespace from your repository, GitHub automatically detects `.devcontainer/devcontainer.json` and provisions the workspace using the pre-built GHCR image.

---

## 5. Customizing & Extending the Image

If your project requires additional system libraries, packages, or specific CLI tools, create a `.devcontainer/Dockerfile` that extends the published base image:

### `.devcontainer/Dockerfile`
```dockerfile
FROM ghcr.io/dan-petty/devops-cli/devcontainer:v0.1.11

# Switch to root to install custom system packages
USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    redis-tools \
    && rm -rf /var/lib/apt/lists/*

# Switch back to non-root developer user
USER vscode
```

### Corresponding `.devcontainer/devcontainer.json`
```json
{
  "name": "my-extended-project",
  "build": {
    "dockerfile": "Dockerfile"
  },
  "mounts": [
    "source=${localEnv:HOME}/.ssh,target=/home/vscode/.ssh,type=bind,consistency=cached"
  ],
  "remoteUser": "vscode"
}
```

---

## 6. Configuring AI Reviewers & Model Context Protocol (MCP)

Inside the Dev Container, `devops-cli` is accessible globally. You can configure AI reviewers and MCP servers for automated agentic pairing:

```bash
# Configure LLM provider credentials securely via OS Keyring
devops ai config --provider claude
devops config set ai.api_key "sk-ant-..."

# Verify connectivity
devops ai test

# Run multi-persona code review on your project diffs
devops ai review branch main
```

To connect external IDE tools to the container's FastMCP server:
```json
{
  "mcpServers": {
    "devops-cli": {
      "command": "uv",
      "args": ["run", "devops", "mcp", "serve"]
    }
  }
}
```

---

## 7. Troubleshooting & Common Questions

### `403 Forbidden` / `Authentication Required`
GHCR packages for `devops-cli` are public. If Docker prompts for credentials when pulling:
```bash
docker logout ghcr.io
docker pull ghcr.io/dan-petty/devops-cli/devcontainer:latest
```

### Docker-in-Docker Permissions
The container runs as non-root user `vscode` with group access to the Docker socket. To verify Docker daemon access inside the container:
```bash
docker ps
```
