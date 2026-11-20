# Proposal: #6409

## Why

`devops install-tools` installed OpenSpec and Style Dictionary from the package folders `src/devops_cli/tools_lock/openspec/` and `src/devops_cli/tools_lock/style-dictionary/` (#6409). Both tools write committed text: the OpenSpec skills and the design tokens. `version_finding` compared the version of the `openspec` on PATH with `tools.lock`. Since #6414, the devcontainer takes OpenSpec from the devtools image. So a devtools update failed the openspec row until `tools.lock` moved, and a move of `tools.lock` failed it until the devtools update came: a cycle that the owner direction of 2026-11-20 forbids. devops-cli is also not a package manager.

## What Changes

- Add `package.json` and `package-lock.json` at the root, with `@fission-ai/openspec` 2.1.0 and `style-dictionary` 5.8.0 as devDependencies and the `glob` and `minimatch` overrides scoped under `style-dictionary`. `.gitignore` ignores `/node_modules/`.
- `devops openspec check`, `regenerate`, `archive`, `new` and `devops roadmap plan-check` run `node_modules/.bin/openspec` of the checkout when it exists, else the `openspec` on PATH. `version_finding` compares the printed version with the `@fission-ai/openspec` version of the root `package-lock.json` of the checkout, and reports a lockfile that pins none. The hint names `npm ci --ignore-scripts`.
- The `audit` row runs `npm audit --prefix .` over the root lockfile, and an ignore names it as `package-lock.json`.
- `devops research inventory` reads the root `package-lock.json`.
- Delete the two package folders and their `tools.lock` entries, the OpenSpec version check of `devops install-tools` and the unused `path_version`.
- The devcontainer runs `npm ci --ignore-scripts` after post-create and puts `node_modules/.bin` on `PATH`. CI jobs that run OpenSpec or Style Dictionary run `npm ci --ignore-scripts`. `make design-tokens` calls `node_modules/.bin/style-dictionary`.
- The `openspec` stage of `Dockerfile` installs the root lockfile with `npm ci --omit=optional --ignore-scripts` in the `node` stage and prunes it to OpenSpec, so the Service and MCP server images no longer take OpenSpec from the devtools image. The runner stages do not change: the runner Job gets the project OpenSpec through the coder bootstrap of #6517.
- Renovate's npm manager updates the root manifest and lockfile. The two custom managers go, and the OpenSpec rule matches the npm manager with its note.
- The change modifies observable command behavior, so it carries spec deltas. It fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `openspec-check`: The gate reads the version of the command on PATH, The gate runs the OpenSpec that npm installed in the checkout
- `openspec-regenerate`: Regenerate reads the version before it writes, The version finding names the path, the versions and the hint
- `tools-lock-install`: The check reads the version the openspec command prints (removed), Only-missing installs openspec when PATH holds another version (removed), The check judges each tool by its link
- `ci-dependency-audit`: Audit reads the root npm lockfile
- `research-inventory`: The inventory lists each pin as a typed component
- `ci-fail-to-pass`: A fix that changes no source code needs no proof
- `ci-service-image-tests`: The in-image suite runs nightly and on image pull requests
- `container-image-layers`: The Dockerfile takes its tools from the devtools image, The Service image runs OpenSpec of the devtools image (removed), The Service image runs OpenSpec of the root lockfile
- `roadmap-service-deployment`: The Service image runs the pinned OpenSpec (removed), The Service image runs the OpenSpec of package-lock.json

## Impact

- Code: `src/devops_cli/openspec/tool.py`, `src/devops_cli/openspec/gate.py`, `src/devops_cli/openspec/scaffold.py`, `src/devops_cli/commands/openspec.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/commands/install_tools.py`, `src/devops_cli/commands/ci.py`, `src/devops_cli/config/commands.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/research/tool_pins.py`, `src/devops_cli/tools_lock/versions.py`, `src/devops_cli/tools_lock/tools.lock`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`.
- Build and CI: `package.json`, `package-lock.json`, `.gitignore`, `.dockerignore`, `Dockerfile`, `Makefile`, `.devcontainer/devcontainer.json`, `.github/workflows/ci.yml`, `.github/workflows/pr-title.yml`, `.github/workflows/copilot-setup-steps.yml`, `.github/workflows/service-image-test.yml`, `.github/renovate.json`, `.pre-commit-config.yaml`.
- Documents: `CONTRIBUTING.md`, `docs/DESIGN.md`, `docs/DEVCONTAINER_USAGE.md`, `docs/SDLC.md`, `docs/commands/install-tools.md`, ADR 0010 and ADR 0024 (Status History lines).
- A new worktree needs `npm ci --ignore-scripts` before `devops openspec check` or `make design-tokens` uses the pin; without it, the gate runs the `openspec` on PATH and fails when its version is not the pin.

## Feasibility

- `npm ci --ignore-scripts && node_modules/.bin/openspec --version && node_modules/.bin/style-dictionary --version` printed `2.1.0` and `5.8.0`, and `npm ls @fission-ai/openspec style-dictionary` exited 0 (npm 12.2.2, Node 24.22.3).
- `podman build --target openspec` of the new stage exited 0; in the image, `openspec.js --version` printed `2.1.0`, `node_modules` held 50 packages, and no `style-dictionary`.
- The four `style-dictionary build -c design/sd/<config>.json` runs from `node_modules/.bin` left `docs/assets/css` and `src/devops_cli/design` unchanged.
- The gate and command tests of group 1 failed on the base (10 failures, among them `DependencyError` for the project install and no finding for a moved pin) and pass after the change.

## Existing Tool Considered

npm/cli (`https://github.com/npm/cli`), which the repository already uses: a root `package.json` with devDependencies and `npm ci`, which refuses a lockfile that does not match the manifest and checks the sha512 of each package. Renovate's built-in npm manager updates both files. The change deletes `src/devops_cli/tools_lock/openspec/`, `src/devops_cli/tools_lock/style-dictionary/`, their `tools.lock` entries and two Renovate custom managers, the OpenSpec version check of `devops install-tools` (`_version_state`, `_version_problem`, `_version_line`) and `path_version`. Only the OpenSpec version guard stays custom, because npm does not compare the binary that a command runs with the lockfile.
