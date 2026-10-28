# Design

## Context

The devcontainer image installs a copy of devops-cli into the system site-packages. The published image needs that copy, because child repositories run `devops` from it. In this repository, the checkout is installed as an editable package in `.venv`, on the volume `devops-cli-venv`. `.devcontainer/devcontainer.json` sets no `PATH`, so a shell that does not activate `.venv` finds `/usr/local/bin/devops` first.

## Decisions

### 1. Put `.venv/bin` first on `PATH` with `remoteEnv`

`.devcontainer/devcontainer.json` sets:

```json
"remoteEnv": {
  "PATH": "${containerWorkspaceFolder}/.venv/bin:${containerEnv:PATH}"
}
```

The Dev Containers CLI and the editor apply `remoteEnv` to terminals, tasks, `devcontainer exec` and the lifecycle commands. When `.venv/bin/devops` exists, `devops` runs the checkout. When the volume is still empty, the lookup goes on to `/usr/local/bin/devops`, so the first post-create still runs.

Rejected alternatives:

- **`ENV PATH` in the Dockerfile**: The Dockerfile builds the published image, which does not know the workspace folder of a child repository. A fixed `/workspaces/devops-cli/.venv/bin` would point every child repository at a folder that does not exist.
- **`containerEnv.PATH`**: The Dev Containers CLI 0.89.0 gives `containerEnv` to `docker run -e` when it creates the container, before it can read the `PATH` of the container. So `containerEnv.PATH` must be a literal, and a literal drops the entries that the Dev Container Features add, such as the Node.js directory.
- **Remove the system install from the image**: Child repositories run `devops devcontainer post-create` and `post-start` from the image (`devcontainer.json.j2`), `.github/actions/devcontainer-smoke` runs `devops --version` in it, and the first post-create of this repository runs before `.venv` holds the checkout. All of them would fail.
- **`remoteEnv` in `.devcontainer/image/devcontainer.json`**: The CLI writes this configuration into the `devcontainer.metadata` label that child repositories read. `.venv/bin` is a setting of this workspace, and #1898 keeps workspace settings out of the image configuration.
- **A live check that a new terminal's `devops --version` equals `uv run devops --version`**: The workspace configuration asks for `--gpus all` and binds the host's `~/.ssh`, so `devcontainer up` with it cannot run on a GitHub runner. The `DevContainer Image` check builds the image configuration, which does not hold `remoteEnv`. The invariant test holds the configuration instead, and it runs in the devcontainer and on a GitHub runner.

### 2. Hold the result with an invariant test

`tests/invariants/test_devcontainer_config.py` parses `.devcontainer/devcontainer.json` and `.devcontainer/image/devcontainer.json`. It asserts the `remoteEnv` of the workspace configuration as one value and asserts that the image configuration has no `remoteEnv`. A change that removes the `PATH` entry, or moves it into the image configuration, fails the test.

## Risks / Trade-offs

- `remoteEnv.PATH` replaces the `PATH` that the CLI reads from the login shell of the user for the lifecycle commands. Entries that `~/.zshrc` adds, such as `~/.local/bin`, are not on `PATH` in post-create and post-start. An interactive zsh reads `~/.zshrc` again and adds them back. Post-create and post-start do not look up a tool in `~/.local/bin` by `PATH`: `uv`, `pre-commit`, `kubectl`, `minikube` and `claude` come from the image and its Features, and `devops install-tools --only-missing` checks the links in its target directory, not `PATH`.
- A shell that `~/.zshrc` changes can put `~/.local/bin` before `.venv/bin`. `~/.local/bin` holds no `devops`, so `devops` still resolves to `.venv/bin/devops`.
