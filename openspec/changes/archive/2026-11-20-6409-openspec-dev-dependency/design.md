# Design

## Decisions

- **Read the pin from the root `package-lock.json` of the checkout.**: `locked_version` in `src/devops_cli/openspec/tool.py` reads `packages["node_modules/@fission-ai/openspec"].version`. It needs no subprocess and no `node_modules`, so the guard also works in a fresh clone.
- **Run `node_modules/.bin/openspec` of the checkout before the `openspec` on PATH.**: `isolated_openspec(root)` takes the binary that `npm ci` installed when it exists. So the OpenSpec of the devtools image has no effect on a gate in the devcontainer, in CI or in a Job after the coder bootstrap of #6517 runs `npm ci`. The callers that know the checkout pass it: check, regenerate, archive, new and `devops roadmap plan-check`. The stage job and the plan recheck keep the `openspec` on PATH: the Service runs them, and its image installs OpenSpec from the same lockfile.
- **Keep the PATH fallback.**: The Service runs the stage gate in a checkout with no `node_modules`, and a runner Job has no `npm ci` until #6517 merges. The version guard still fails a binary that is not the pin, with the hint `npm ci --ignore-scripts`, so the fallback cannot write other skill text.
- **Install in the devcontainer with the `postCreateCommand`, not in `devops devcontainer post-create`.**: The spec `devcontainer-image-tools` keeps post-create free of tool installs. `npm ci --ignore-scripts` after it installs the lockfile of the workspace, and `remoteEnv` puts `node_modules/.bin` on `PATH` after `.venv/bin`.
- **Install the Service OpenSpec from the root lockfile in the `node` stage.**: The `openspec` stage copies `package.json` and `package-lock.json`, runs `npm ci --omit=optional --ignore-scripts`, removes the `style-dictionary` devDependency and the overrides, and prunes offline. The image keeps only OpenSpec and its packages, as before.
- **Audit the root lockfile with `--prefix .`, and name it `package-lock.json`.**: `npm_audit_lockfile` joins the prefix and the file name as a POSIX path, so an ignore entry names the root lockfile without `./`.
- **A bump of a pin edits no file under `src/` or `tests/`.**: The owner direction of 2026-11-20 asks that a Renovate update of `package.json` and `package-lock.json` pass CI alone. No file under `src/` or `tests/` holds the version of OpenSpec or Style Dictionary. The OpenSpec fake answers `--version` with the version that the `package-lock.json` of the repository pins, and no test compares the version of the record with the pin. A run of the OpenSpec and audit tests with both pins moved to versions that do not exist passed with no other edit.
- **Keep the Renovate OpenSpec rule and add `matchManagers: ["npm"]`.**: The rule keeps its group, schedule and notes, and the first note names `npm ci --ignore-scripts`. No new group is added.

## Rejected alternatives

- **Run `npm ls @fission-ai/openspec` in the guard**: `npm ls` exits 1 when `node_modules` is absent, so it cannot report the version difference that the gate must name.
- **Keep the package folders and `tools.lock` entries**: The owner direction of 2026-11-19 says devops-cli is not a package manager, and the cycle with the devtools image stays.
- **Require `node_modules/.bin/openspec` with no PATH fallback**: The Service checkout has no `node_modules`, and a runner Job has none until #6517, so the stage gate and the openspec row of a Job would fail until then.
- **Install the tools in the devcontainer image build**: The devcontainer image comes from the devtools image (#6414), and a rebuild is the only way to change a tool there; the lockfile of the checkout must decide the version.
- **Make `devops install-tools --tool openspec` print the `npm ci` hint**: It keeps a special case for a tool that the lock no longer holds; the unknown-tool error lists the tools, and each document names `npm ci --ignore-scripts`.
- **Give the runner image OpenSpec in this change**: The owner direction of 2026-11-20 gives the runner Job the project OpenSpec through the coder bootstrap of #6517, so this change leaves the runner stages alone.
