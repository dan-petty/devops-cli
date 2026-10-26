# Design

## Context

See `proposal.md` for motivation.
Dev Containers CLI writes the configuration properties into the OCI image label `devcontainer.metadata` when building a devcontainer image.
Downstream / child devcontainers that use the image automatically inherit all properties in `devcontainer.metadata`.
To isolate the image build metadata from the repository's development workspace settings, we use the upstream two-configuration pattern.

## Goals / Non-Goals

**Goals:**
- Provide a clean `.devcontainer/image/devcontainer.json` configuration that builds the container image with its features and common container environment.
- Keep the `devops-cli` workspace configuration `.devcontainer/devcontainer.json` for developing `devops-cli` (with local volumes, cache mounts, lifecycle hooks, and editor customizations).
- Update `.github/actions/devcontainer-image/action.yml` to build the new image configuration.
- Enforce in tests that the image configuration contains no volume mounts, lifecycle commands, or editor customizations, and that the features and lockfiles stay synchronized.

**Non-Goals:**
- Change the features installed in the image.
- Change the base Dockerfile or tool bootstrap steps.
- Modify how `devops devcontainer init` scaffolds child repositories (child repositories already point to the published image and provide their own mounts).

## Decisions

### 1. Two-configuration directory layout

We place the image build configuration in `.devcontainer/image/devcontainer.json` with its companion `.devcontainer/image/devcontainer-lock.json`.
- `build.dockerfile`: `"../Dockerfile"`
- `build.context`: `"../.."`
- `features`: Identical to `.devcontainer/devcontainer.json`
- `remoteUser`: `"vscode"`
- `containerEnv`: Standard container environment (Git credential helpers, telemetry opt-outs, `DEVOPS_CLI_CONFIG`, `DBUS_SESSION_BUS_ADDRESS`, `UV_MALWARE_CHECK`). `UV_CACHE_DIR` is omitted because it binds to the workspace-specific volume mount.
- `mounts`: Omitted entirely.
- `postCreateCommand` / `postStartCommand`: Omitted entirely.
- `customizations`: Omitted entirely.

*Rejected alternatives:*
- *Post-build label stripping*: Stripping `devcontainer.metadata` after build using a custom script or Docker build manipulation.
  *Evidence that rejected it*: Dev Containers CLI relies on `devcontainer.metadata` to know the remote user (`vscode`) and feature metadata (feature environment, PATH entries). Stripping the label breaks feature execution in child containers.
- *Single configuration with command-line overrides*: Using `--override-config` or command-line flags on `devcontainer build`.
  *Evidence that rejected it*: Dev Containers CLI embeds the parsed configuration into the image label; `--override-config` cannot strip existing properties without a separate clean file.

### 2. Synchronization between workspace and image configurations

We maintain both `.devcontainer/devcontainer.json` and `.devcontainer/image/devcontainer.json`.
An automated test asserts that:
- The `features` object of `.devcontainer/image/devcontainer.json` equals the `features` object of `.devcontainer/devcontainer.json`.
- The `features` object of `.devcontainer/image/devcontainer-lock.json` equals the `features` object of `.devcontainer/devcontainer-lock.json`.
- Renovate bot already matches `.devcontainer/<folder>/devcontainer.json` according to upstream Renovate defaults.

*Rejected alternatives:*
- *Dynamic generation of image config during CI build*:
  *Evidence that rejected it*: Dev Containers CLI expects a committed `devcontainer-lock.json` alongside the config for reproducible, frozen builds (`--frozen-lockfile`). Generating at CI runtime prevents Renovate from auditing and locking feature dependencies.

### 3. Update the composite action `.github/actions/devcontainer-image`

The action generates `.devcontainer/image/devcontainer.build.json` with build labels and options injected, and runs `devcontainer build` with `--config .devcontainer/image/devcontainer.build.json`.

## Risks / Trade-offs

- [Configuration drift between workspace and image features] → Mitigated by an automated invariant test asserting exact equality of features and lockfiles.
- [Dev Containers CLI path resolution in subdirectories] → Mitigated by setting `build.dockerfile: "../Dockerfile"` and `build.context: "../.."` and verifying with `@devcontainers/cli` 0.89.0.
