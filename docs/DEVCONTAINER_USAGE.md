# Using the Published DevOps CLI Dev Container

`devops-cli` publishes pre-built, production-ready Dev Container images to the GitHub Container Registry (**GHCR**) on every release. You can use these published images directly in downstream repositories, GitHub Codespaces, and workstation environments without having to build the container or compile dependencies locally.

---

## 1. Published Container Images & Tags

The official image, for `linux/amd64`, is hosted on GHCR at:
`ghcr.io/dan-petty/devops-cli/devcontainer`

The release builds the image from `.devcontainer/image/devcontainer.json` and `.devcontainer/Dockerfile` with the Dev Containers CLI. `.devcontainer/Dockerfile` builds FROM the devtools image `ghcr.io/dan-petty/devtools` at a digest that Renovate moves. So the image holds the tools of the devtools image, the Dev Container Features of that file and the user `vscode` (uid 1000, gid 1000). When a repository names only the image, the `devcontainer.metadata` label of the image sets the remote user to `vscode`. The release starts each image as `vscode` before it tags the image. Images `v0.2.35` to `v0.2.38` have no features and no user `vscode`, and neither had `latest` while one of them was current. A configuration with `"remoteUser": "vscode"` cannot open them ([#1895](https://github.com/dan-petty/devops-cli/issues/1895)). Use `v0.2.34`, or a release after `v0.2.38`. `v0.2.34` and earlier releases have only `linux/amd64`.

| Tag Pattern | Example | Description | Best For |
| :--- | :--- | :--- | :--- |
| `latest` | `ghcr.io/dan-petty/devops-cli/devcontainer:latest` | Latest official stable release | Default development environments |
| `v<version>` | `ghcr.io/dan-petty/devops-cli/devcontainer:v<version>` | Immutable, pinned version (a published release tag) | CI pipelines & reproducible environments |
| `sha256:...` | `ghcr.io/dan-petty/devops-cli/devcontainer@sha256:...` | Cryptographic digest pinning | Zero-trust compliance & air-gapped builds |

### Pulling the Image Directly
```bash
# Pull the latest published image
docker pull ghcr.io/dan-petty/devops-cli/devcontainer:latest

# Or pull a specific pinned release
docker pull ghcr.io/dan-petty/devops-cli/devcontainer:v<version>
```

---

## 2. Pre-Installed Tooling & Capabilities

The published Dev Container image is built FROM the devtools image ([dan-petty/devtools](https://github.com/dan-petty/devtools)), which is `debian:sid` (Debian Unstable) with Python 3.14 and the cloud-native, DevOps and AI developer tools. The README of the devtools image names the source and the version file of each tool. The image adds the venv of `devops-cli` in `/opt/devops-cli/.venv`, the last directory of `PATH`, and two Dev Container Features:

- **Runtimes & Package Managers**: Python 3.14+, `uv` (ultra-fast package & virtualenv manager), `git`, `zsh` with Oh My Zsh.
- **Containers (Podman)**: The `podman-in-podman` Feature with `dockerCompat` runs Podman in the container. The image has no Docker CLI and no Docker engine. For `vscode`, `podman` and `docker` (the `podman-docker` package, which runs `podman`) use rootless Podman, and `docker compose` and `podman compose` run `podman-compose`, rootless and with no socket. `/var/run/docker.sock` is the socket of a rootful Podman API service, and the Docker SDK of `devops docker` uses it. The `remoteEnv` of the image sets `DOCKER_HOST=unix:///var/run/docker.sock`: a bash login shell under the VS Code server reads `/etc/profile.d/podman-docker.sh`, which otherwise sets `DOCKER_HOST` to a rootless socket where no service runs. `podman` and `podman-compose` do not read `DOCKER_HOST`. The Feature makes the container privileged, as `docker-in-docker` did.
- **Two image stores**: `docker`, `podman` and `docker compose` as `vscode` use the rootless store. `devops docker images`, `devops docker build`, `devops docker push` (the Docker SDK), `sudo podman` and `sudo docker` use the rootful store. So an image from `docker build` is not visible to `devops docker push`. To copy it, run `podman save <image> | sudo podman load`. The output of `docker info` and of other `docker` commands is the output of Podman, and it can differ from the output of Docker.
- **inotify watches**: On `debian:sid`, aardvark-dns 1.17 puts an inotify watch on `/etc/resolv.conf`. When the VS Code server holds almost all inotify watches of the host user, rootless `docker compose` cannot resolve container names (`ping: bad address`), and the removal of a rootful network can fail (`aardvark-dns failed to start`). `.vscode/settings.json` already excludes the agent worktrees and the clones from the VS Code file watcher ([#6453](https://github.com/dan-petty/devops-cli/issues/6453)). If the limit is still reached, raise `fs.inotify.max_user_watches` on the WSL2 host.
- **Kubernetes & Cloud Native**: `kubectl`, `helm`, `minikube` (with optional GPU passthrough support), `kustomize`. The docker driver of Minikube with `podman-docker` is not tested ([#6466](https://github.com/dan-petty/devops-cli/issues/6466)).
- **Dev Container Features**: `.devcontainer/image/devcontainer.json` has two Features: `common-utils` (the user `vscode`, uid and gid 1000, and zsh) and `podman-in-podman`. No Feature option names a tool version: each tool comes from the devtools image. `.devcontainer/image/devcontainer-lock.json` pins the digest of each Feature, and the image build runs with `--frozen-lockfile`. Renovate's devcontainer manager changes the tag of a Feature but has no code for the lockfile. So after a Feature bump, run `devcontainer upgrade --workspace-folder . --config .devcontainer/image/devcontainer.json` and commit the lockfile in the same pull request. A case of `tests/invariants/test_devcontainer_config.py` fails on a feature that the lockfile does not resolve.
- **Infrastructure as Code**: `devops tf` wraps OpenTofu or Terraform. The image has `tofu` and `tflint`; install `terraform` yourself.
- **Security & Compliance Integrations**: runners for `bandit`, `trivy`, `semgrep`, `gitleaks`, `kube-linter`, `kubeconform`, `pluto` and `actionlint` (`devops scan`, `devops k8s`, `devops ci`). Trivy's misconfiguration scan (`devops scan trivy --type config`) scans the IaC files. These tools and `gitleaks` and `osv-scanner` come from the devtools image. Its commands are in `/usr/local/bin`, and the files of a Python or Node tool are in `/usr/local/lib/devtools`. `devops devcontainer post-create` installs no tool: a new devtools digest in `.devcontainer/Dockerfile` and a rebuild of the image change a tool. OpenSpec and Style Dictionary are devDependencies of the project: the `postCreateCommand` of `.devcontainer/devcontainer.json` runs `npm ci --ignore-scripts` after post-create, which installs them at the versions of `package-lock.json` into `node_modules/.bin`, and `remoteEnv` puts that directory on `PATH` after `.venv/bin`. The project commands call them from `node_modules/.bin` of the checkout, so the `openspec` of the devtools image has no effect on them (#6409). `devops repos worktrees add` runs `npm ci --ignore-scripts` in a new worktree, so `devops openspec check` and `make design-tokens` find the pinned versions there.
- **Terminal tools**: The image installs `k9s`, a terminal dashboard for Kubernetes, `gh-dash`, a terminal dashboard for GitHub pull requests and issues, and `tuicr`, a terminal program that shows a diff and lets a person add typed comments, from the devtools image in `/usr/local/bin`. Post-create installs no tool. A person starts `gh-dash` at the root of the clone with `gh-dash --config .gh-dash.yml`. The file `.gh-dash.yml` shows the pull requests oldest first and the issues for triage, and it refreshes every 60 minutes with the preview closed. The first start also writes `~/.config/gh-dash/config.yml`. Agents never start `gh-dash`.
- **Reviewing an agent diff with `tuicr`**: A person uses `tuicr` to review the diff of an agent. The person copies `.devops/tuicr.config.toml` to `~/.config/tuicr/config.toml` once, after a backup of any existing file with the suffix `.bak-<YYYYMMDD-HHMMSS>`. The template turns off the update check, which otherwise calls `crates.io` at start, and defines the comment types `issue`, `question` and `nit`. In the worktree of the agent, the person starts `tuicr -r origin/main..HEAD` for the commits or `tuicr -w` for the uncommitted changes. Nobody runs `tuicr pr`, `tuicr update` or `curl | sh`, and agents never start `tuicr`. The "Human Review Round" bullet of [`SDLC.md`](SDLC.md) Phase 6 gives the rules for agents.
- **What `gh-dash` sends and can do**: At start, `gh-dash` sends one GraphQL request to `api.github.com` that asks for its latest release, and it has no switch to stop this request. Its approve, merge, close, ready, reopen, update, assign, label and comment keys stay active and use the token of the person who runs it. `gh-dash` still draws some icons with Nerd Font glyphs, in its preview pane, its notification rows and some column headers. `.gh-dash.yml` hides the icon cells of the tables, holds only ASCII and sets no glyph.
- **What `gh-dash` costs at start**: The GitHub budget is 5,000 GraphQL points an hour for the token, and AI agents use the same token. The source of `gh-dash` 4.26.2 gives the request counts, and GitHub dry runs give the points of one request. At start, `gh-dash` reads the login of the person (1 point) and checks its latest release (1 point). It fetches only the sections of the view that it starts on, which are the 4 pull request sections of `.gh-dash.yml`. A pull request section costs 1 point at `limit: 20` and 2 points at `limit: 50`, so the 4 sections cost 5 points. So `.gh-dash.yml` costs 7 points at start. A count of the log lines of one start with the first config showed one section fetch more than the source gives. These 7 points do not include that fifth fetch.
- **What `gh-dash` costs an hour**: A refresh fetches every section of the view on screen, and the pull request view costs 5 points. `.gh-dash.yml` refreshes every 60 minutes, so it costs 5 points an hour. An open preview adds 2 points at start, 2 points at each refresh and 2 points for each row that a person selects. The preview starts closed, and the `p` key opens it. A person who keeps the preview open and refreshes every 15 minutes pays about 28 points an hour.
- **Measuring what `gh-dash` costs**: To count the requests of one start, a person runs `gh-dash --debug --config <path-to-clone>/.gh-dash.yml` in a scratch directory. The person lets it run for 60 seconds, then closes it. The person counts the lines `Fetching PRs`, `Fetching PR ` (with a space at the end), `Fetching issues` and `Fetching latest version` in `debug.log`, then deletes the file. Count these lines. Do not read the quota counters of `devops gh rate-limit` before and after. The rate-limit window can roll between the two reads, and every other tool that uses the token changes the counters.
- **First count of the log lines**: On 2026-10-22, on a quiet machine, a person ran this count with the first config (refresh every 15 minutes, preview open). `debug.log` held 5 lines `Fetching PRs`, 0 lines `Fetching PR `, 0 lines `Fetching issues` and 1 line `Fetching latest version`. The source study expected 4 section fetches, 1 fetch of the selected row, 0 issue fetches and 1 version check. The log shows one more section fetch than expected and no fetch of the selected row. Nobody has confirmed the cause of the fifth fetch. A probable cause is a fetch of the next page when the window gets focus, for a section that has more matches than its limit. Nobody has confirmed why the fetch of the selected row did not occur: the preview may not open at start, or the log text may differ.
- **Why the quota counters cannot assign a cost**: In the same measurement, the `graphql` value of `devops gh rate-limit` went from 51 to 7, so the rate-limit window rolled between the two reads. The `core` value moved by +1, because each run of the command costs 1 core point and 1 GraphQL point. Other tools use the same token. So an earlier jump of +124 GraphQL points in 22 seconds cannot be assigned to `gh-dash`. The counted fetches match the computed cost of about 9 points for the first config.
- **Sandbox Confinement & Host Isolation**: Linux bubblewrap (`bwrap`) pre-installed for unprivileged namespace confinement of executable verification criteria and untrusted code execution. `socat` is pre-installed for the `kube-api` network profile: it relays the Kubernetes API server into the sandbox of a Popeye scan (`SECURITY.md`). Criteria run the reviewed repository's own `.venv/bin` first on `PATH`, so `python` and `ruff` are the project's; run `uv sync` in that repository before a review, or criteria fall back to the system's `/usr/bin` tools.
- **Network diagnostics**: The image has `ping`, `tracepath`, `traceroute`, `mtr`, `nc` (OpenBSD netcat), `tcpdump`, `dig` and `nslookup`. The user `vscode` runs each of them with no `sudo`, except `tcpdump`:
  - `ping` opens an ICMP echo socket and has no file capability. The run argument `--sysctl=net.ipv4.ping_group_range=1000 1000` lets the group of `vscode` (gid 1000) open this socket. `devops devcontainer init` and the manual configuration of section 3 write the run argument. When the run argument applies, `cat /proc/sys/net/ipv4/ping_group_range` shows `1000 1000`. Without the run argument, rootless Podman lets only group 0 open the socket, so use `sudo ping`. Also use `sudo ping` when the gid of `vscode` is not 1000: on a Linux host, VS Code can change the gid of `vscode` to the gid of the host user (`updateRemoteUserUID`). Under rootless Podman with `keep-id`, the range must start at 1000, because the kernel compares host group IDs, and gid 1000 maps to a host ID below the host IDs of the other groups of the container. A bound that the user namespace does not map, for example `2147483647`, stops the container at its start.
  - `mtr` opens its raw socket through `mtr-packet`, which gets the `cap_net_raw` file capability from its Debian package.
  - `tcpdump` needs a packet socket, so use `sudo tcpdump`. The image gives `tcpdump` no file capability, because that capability lets every user of the container capture packets.
  - Rootless Podman connects the container to the network through pasta, and pasta sends each ICMP echo through a socket of the host. So the destination answers each ICMP probe, and `mtr` and `traceroute -I` show only the destination. `tracepath` and `traceroute` send UDP probes and show each hop.
- **AI Code Review & MCP Integration**: `devops-cli` suite pre-installed with Model Context Protocol (FastMCP) server endpoints (`devops mcp serve`), OpenTelemetry instrumentation, and Logfire.

---

## 3. Quickstart: Adding to Your Project

### Option A: Using the CLI (Recommended)

You can scaffold a complete, best-practice `.devcontainer/` setup targeting the published image using `devops devcontainer init`:

```bash
# Initialize a new project with the published GHCR container image
devops devcontainer init --name my-project

# --image currently writes :latest for devops-cli images; pin by editing "image" in the generated .devcontainer/devcontainer.json
devops devcontainer init --name my-project --image ghcr.io/dan-petty/devops-cli/devcontainer:v<version>
```

This scaffolds:
1. `.devcontainer/devcontainer.json`: Pre-configured manifest using the published image with `/tmp`, persistent user home volume, SSH directory forwarding, post-create lifecycle commands (`devops devcontainer post-create`), and IDE extensions. The file has no Dev Container Feature: the image supplies the user `vscode` and the tools. The `devcontainer.metadata` label of the published image also gives `remoteEnv`, for example `DOCKER_HOST`. An image that `--image` names must have the user `vscode` and the tools. `--minikube` (the default) only forwards the ports of the services of the Minikube stack.
2. `.vscode/mcp.json`: Model Context Protocol configuration exposing `devops-cli` tools to AI coding assistants (Claude Desktop, Cursor, VS Code, Antigravity IDE).
3. `AGENTS.md`, `CLAUDE.md`, `GEMINI.md` and `.github/copilot-instructions.md`: The rules for every agent task, and a table that routes each task to its document.
4. `.mcp.json`: the same MCP server for Claude Code.
5. `kilo.jsonc`: the same MCP server for Kilo Code. Kilo Code reads `AGENTS.md` itself, so it needs no pointer stub.

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
    "UV_MALWARE_CHECK": "0",
    "UV_CACHE_DIR": "${containerWorkspaceFolder}/.uv"
  },
  "postCreateCommand": "UV_MALWARE_CHECK=1 uv sync",
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
  "runArgs": [
    "--sysctl=net.ipv4.ping_group_range=1000 1000"
  ],
  "remoteUser": "vscode"
}
```

> [!TIP]
> **Optional GPU Acceleration (NVIDIA Hosts)**: If running on a host with an NVIDIA GPU and `nvidia-container-toolkit` installed, pass GPUs to the container by adding `--gpus all` to `runArgs`:
> ```json
> "runArgs": ["--gpus", "all", "--sysctl=net.ipv4.ping_group_range=1000 1000"]
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
FROM ghcr.io/dan-petty/devops-cli/devcontainer:v<version>

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

### The Devcontainer of This Repository
`.devcontainer/devcontainer.json` of `devops-cli` uses the published image `ghcr.io/dan-petty/devops-cli/devcontainer:latest`, as a child repository does. `.devcontainer/image/devcontainer.json` and `.devcontainer/Dockerfile` are the only build definition. The `devcontainer.metadata` label of the image gives the features, their run options, the remote user and the environment, so the workspace file holds only the mounts, the run arguments, the `PATH` of the checkout's `.venv`, the lifecycle commands and the editor settings.
- **A new release**: a rebuild uses the local copy of the tag. Pull the tag first, then run `Dev Containers: Rebuild Container`:
  ```bash
  podman pull ghcr.io/dan-petty/devops-cli/devcontainer:latest
  ```
  After a rebuild, run `uv sync --all-groups --all-extras` once. Until `.venv` is full, `devops` is the copy in the image.
- **An image change before a release**: CI builds and starts the image for each pull request that changes an image input other than `src/`, such as `.devcontainer/` or `uv.lock`, and daily from `main` ([SDLC.md](SDLC.md#the-devcontainer-image-devcontainer-imageyml-devcontainer)). To use the change in your own container first, build the Feature image and add the project layer:
  ```bash
  jq '.build.target = "base"' .devcontainer/image/devcontainer.json > /tmp/devcontainer.base.json
  devcontainer build --workspace-folder . --config /tmp/devcontainer.base.json --image-name devops-cli-devcontainer-base:local
  docker buildx build --file .devcontainer/Dockerfile --target project --build-arg BASE_IMAGE=devops-cli-devcontainer-base:local -t devops-cli-devcontainer:local .
  ```
- **Mounts that hold data**: the `.data` volume (agent worktrees and state), the home volume (the keyring and its copies, shell history, tool logins), the bind mount of the host `~/.ssh` and the `/tmp` volume. A test fails if one of them leaves the file. Before a change to the mounts or the image, export the volumes on the host:
  ```bash
  mkdir -p ~/devcontainer-backup
  podman volume export devops-cli-data -o ~/devcontainer-backup/devops-cli-data-$(date +%Y%m%d).tar
  podman volume export global-devcontainer-home -o ~/devcontainer-backup/home-$(date +%Y%m%d).tar
  cp -a ~/.ssh ~/devcontainer-backup/ssh-$(date +%Y%m%d)
  ```
- **No cache volumes**: the workspace is on the Linux file system of the host, so `.venv`, `.uv` and the tool caches stay in the checkout, where `.gitignore` excludes them. To remove the cache volumes of an earlier configuration, name each one. Do not use `podman volume prune` or `podman system prune --volumes`: while a rebuild has removed the container, no container uses the `.data` and home volumes, and a prune deletes them.
  ```bash
  podman volume rm devops-cli-venv devops-cli-mypy-cache devops-cli-pytest-cache devops-cli-ruff-cache devops-cli-uv
  ```
- **File watcher**: the VS Code file watcher adds one inotify watch for each folder that it watches. All processes of the user share the limit in `/proc/sys/fs/inotify/max_user_watches`. When the watcher uses all watches, other programs cannot add a watch: for example, aardvark-dns stops and container names do not resolve (#6453). `files.watcherExclude` in `.vscode/settings.json` excludes the agent worktrees (`.data/`, `.claude/worktrees/`), the clones (`repos/`), `.venv/` and the tool caches. VS Code adds these patterns to its default excludes and applies a change with no rebuild. `files.exclude` and `search.exclude` do not change the watcher. Add a new folder with many subfolders to the same setting. To count the watches of the file watcher:
  ```bash
  for pid in $(pgrep -u "$(id -u)" -f '[-]-type=fileWatcher'); do echo "$pid $(cat /proc/$pid/fdinfo/* 2>/dev/null | grep -c '^inotify')"; done
  ```

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

# Review the active branch against main
devops review branch

# Or explicitly review a specific feature branch against main
devops review branch feat/123-my-feature --base main

# Run targeted review on a specific directory
devops review path src/
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
- **A workspace on the Linux file system** (for example a clone in the WSL2 home folder) is on the same disk as the volumes, so a cache volume gives no speed. Keep volumes there only for data that must outlive the container, such as `.data`, `/home/vscode` and `/tmp`.

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
- **Unlocking**: the keyring starts locked every time a container starts. The first interactive terminal that you open asks for the password. Only one terminal asks at a time, and none do once the keyring is unlocked. `devops devcontainer post-start` does not ask, because the terminal that VS Code shows while the container starts sends each key two times, so a password typed there is always wrong.

  The first time, you choose the password, so it is asked for twice. Empty passwords are refused, because they would store every secret in plain text. Once the keyring is unlocked, any plaintext `gh` token is moved into it automatically. You can also unlock by hand at any time:
  ```bash
  devops devcontainer unlock-keyring
  ```
- **No GUI prompt**: the session bus and gnome-keyring get no `DISPLAY` and no `WAYLAND_DISPLAY`, so the GUI prompt "Unlock Login Keyring" never opens. A program that asks for a secret while the keyring is locked gets an error at once; unlock in a terminal. gnome-keyring keeps the last password that `--unlock` rejected, and after a successful unlock in its GUI prompt it changes the keyring password to that rejected password, with no message.
- **Copies**: after each successful unlock, `unlock-keyring` copies `~/.local/share/keyrings/login.keyring` to `~/.local/share/keyrings/backups/login.keyring.<UTC time>`, when the file changed since the newest copy. It keeps the 10 newest copies. Each copy opens with the password that unlocked the keyring when the copy was made. To go back to a copy, copy it over the keyring file and unlock:
  ```bash
  cp ~/.local/share/keyrings/backups/login.keyring.<UTC time> ~/.local/share/keyrings/login.keyring
  devops devcontainer unlock-keyring
  ```
- **Moving an existing token in by hand**: if the automatic move is skipped (for example because `GH_TOKEN` is set), move a plaintext `gh` token into the keyring without minting a new one:
  ```bash
  gh auth token -h github.com | gh auth login -h github.com --with-token
  ```
  `devops devcontainer post-start` and `unlock-keyring` both warn about any host that still has a plaintext token, and print this command for it.
- **Git over HTTPS**: The `remoteEnv` of the image routes `github.com` and `gist.github.com` credentials through `gh auth git-credential`, so git uses the same keyring-backed token as `gh`. These `GIT_CONFIG_*` entries are read after every config file, so they override the helper VS Code adds to forward credentials from the host. The first entry of each host is the empty value, which clears the helpers of the files, and the second is `gh`. They are in `remoteEnv` and not in `containerEnv`, so the image build gets no `SecretsUsedInArgOrEnv` warning; `remoteEnv` reaches each process that the Dev Containers tools start, but not a process that `docker exec` starts directly. While the keyring is locked, `git fetch` over HTTPS fails instead of quietly using the host's credentials. Other hosts are unchanged. A `devops` command gives these entries to each child that it starts, so its git calls use the same helper.
- **`devops` secrets**: `devops config` refuses to store a secret while the keyring is locked, and names `unlock-keyring` in the error. `devops k8s push-secrets` and `devops k8s deploy-stack` stop before applying anything while it is locked; unlock it, then run `devops k8s deploy-stack --stack <stack> --context minikube`. It also refuses keyring setups that could fall back to a plaintext backend.

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
    C -->|docker driver on Podman| G[Pods: Monitoring, ArgoCD, Tempo, LLMs]
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

When developing in self-contained environments or GitHub Codespaces, the Dev Container runs an embedded single-node Minikube cluster with the `docker` driver (`--driver=docker`). In the image, `docker` is `podman-docker` (rootless by default), so the bootstrap sets `DOCKER_HOST=unix:///var/run/docker.sock` to direct `podman-docker` to the rootful Podman API socket (`/run/podman/podman.sock`), keeping the live cluster start check on the owner's rootless Podman host and Docker as the merge gate ([#6466](https://github.com/dan-petty/devops-cli/issues/6466)).

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
minikube start --driver=docker --cni=calico --addons=storage-provisioner-rancher --gpus=all   # --gpus=all only when nvidia-smi is present
```
If the container runtime lacks NVIDIA Container Toolkit support or fails to allocate GPUs, DevOps CLI automatically detects the failure and transparently falls back to CPU mode, ensuring container startup never fails due to missing GPU drivers.

#### Add-Ons
devops-cli starts Minikube with the add-on `storage-provisioner-rancher`, which gives the StorageClass `local-path`. The defaults of minikube (`default-storageclass`, `storage-provisioner`) also apply. A Minikube that already runs keeps its add-ons: run `minikube addons enable storage-provisioner-rancher` one time on it. Enable other add-ons with `minikube addons enable ingress` (or `metrics-server`, `dashboard`).

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
- **Zero Information Leakage Compliance**: Never commit private IP addresses (RFC 1918), corporate internal hostnames, or cluster access tokens into `config.yaml` templates, manifests, or change folders. Always use abstract placeholders (`<cluster-name>`, `<region>`, `arn:aws:eks:...`).

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
devops k8s deploy-stack --stack infra     # ArgoCD, k8s-monitoring (Alloy), Prometheus, Grafana, OTel Collector, Tempo
devops k8s deploy-stack --stack llm       # Ollama profiles, LLM gateway, Open WebUI, Qdrant, Valkey
devops k8s deploy-stack --stack logging   # Loki; the infra stack's Alloy ships the logs
devops k8s deploy-stack --stack all       # every stack, also devops and gitea

# 6. Stream logs from a deployed controller
devops k8s stream-logs argocd-server -n argocd --tail 100 -f
```
