# Using the Published DevOps CLI Dev Container

`devops-cli` publishes pre-built, production-ready Dev Container images to the GitHub Container Registry (**GHCR**) on every release. You can use these published images directly in downstream repositories, GitHub Codespaces, and workstation environments without having to build the container or compile dependencies locally.

---

## 1. Published Container Images & Tags

The official multi-architecture (`linux/amd64`, `linux/arm64`) images are hosted on GHCR at:
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

The published Dev Container image is built on Python 3.14 (`trixie`) and includes comprehensive cloud-native, DevOps, and AI developer tooling pre-configured out of the box:

- **Runtimes & Package Managers**: Python 3.14+, `uv` (ultra-fast package & virtualenv manager), `git`, `zsh` with Oh My Zsh.
- **Containers & Virtualization**: Docker-in-Docker (DinD) enabled with rootless socket mapping for non-root user `vscode`.
- **Kubernetes & Cloud Native**: `kubectl`, `helm`, `minikube` (with optional GPU passthrough support), `kustomize`.
- **Infrastructure as Code**: OpenTofu (`tofu`) and Terraform (`terraform`) dual compatibility.
- **Security & Compliance Scanners**: Aqua `trivy`, `semgrep`, `gitleaks`, `checkov`, `bandit`, `pip-audit`, Red Hat `kube-linter`, Fairwinds `pluto`, `actionlint`.
- **AI Code Review & MCP Integration**: `devops-cli` suite pre-installed with Model Context Protocol (FastMCP) server endpoints (`devops mcp serve`), OpenTelemetry instrumentation, and Logfire.

---

## 3. Quickstart: Adding to Your Project

### Option A: Using the CLI (Recommended)

You can scaffold a complete, best-practice `.devcontainer/` setup targeting the published image using `devops devcontainer init`:

```bash
# Initialize a new project with the published GHCR container image
devops devcontainer init --name my-project --published

# Or specify a custom pinned tag
devops devcontainer init --name my-project --image ghcr.io/dan-petty/devops-cli/devcontainer:v0.2.16
```

This scaffolds:
1. `.devcontainer/devcontainer.json`: Pre-configured manifest using the published image with performance-optimized named volumes, cross-platform SSH forwarding, and IDE extensions.
2. `.vscode/mcp.json`: Model Context Protocol configuration exposing `devops-cli` tools to AI coding assistants (Claude Desktop, Cursor, VS Code, Antigravity IDE).
3. `AGENTS.md`: Operational engineering instructions and architectural constraints for AI pair programmers.

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
  "forwardPorts": [
    8080,
    8030,
    8090,
    16686,
    6333,
    6379,
    11434
  ],
  "portsAttributes": {
    "8080": {
      "label": "ArgoCD Web UI",
      "onAutoForward": "notify"
    },
    "8030": {
      "label": "Grafana Dashboard",
      "onAutoForward": "notify"
    },
    "8090": {
      "label": "Prometheus Metrics",
      "onAutoForward": "notify"
    },
    "16686": {
      "label": "Jaeger Query UI",
      "onAutoForward": "notify"
    },
    "6333": {
      "label": "Qdrant Vector DB",
      "onAutoForward": "notify"
    },
    "6379": {
      "label": "Valkey Cache",
      "onAutoForward": "ignore"
    },
    "11434": {
      "label": "Ollama LLM Engine",
      "onAutoForward": "ignore"
    }
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
  "remoteUser": "vscode",
  "runArgs": [
    "--gpus",
    "all"
  ]
}
```

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
# Configure Anthropic Claude API provider
devops ai config --provider claude --api-key "sk-ant-..."

# Or configure local Ollama running on your workstation host
devops ai config --provider ollama --model qwen2.5-coder:7b --ollama-urls http://host.docker.internal:11434

# Verify provider connectivity and latency
devops ai test

# Run multi-persona code review on your feature branch
devops review branch main

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

### Cross-Platform SSH Agent Forwarding
Windows uses `%USERPROFILE%\.ssh` while macOS/Linux use `$HOME/.ssh`. Combining both environment variables in the mount definition ensures cross-platform compatibility without manual edits:
```json
"source=${localEnv:HOME}${localEnv:USERPROFILE}/.ssh,target=/home/vscode/.ssh,type=bind,consistency=cached"
```

### Zero-Root Principle
The published Dev Container executes by default as non-root user `vscode` (UID 1000, GID 1000) with passwordless `sudo` privileges if required. Always ensure custom scripts and daily development commands execute under `vscode` to prevent permission collisions on host-mounted files.
