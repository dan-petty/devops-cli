# Proposal: #7264

## Why
#7233 (pull request #7260) made `devops repos worktrees add` run `npm ci --ignore-scripts` in each new worktree. Its premise was wrong: the `openspec` row of `devops ci` did not find the `openspec` of the image. It found a stale copy in the home volume. `~/.local/bin/openspec` (2.1.0) was a link into `~/.local/share/devops-cli/tools/`, which the removed `devops install-tools` wrote, and the shell profiles of the home volume put `~/.local/bin` first on `PATH`. The link hid the pinned copy (`node_modules/.bin` of the main checkout, 2.2.0, on `PATH` through `remoteEnv` of `.devcontainer/devcontainer.json`) and the copy of the devtools image (`/usr/local/bin`). The stale links are removed. So the step installs 87 MB of Node tools a second time for each worktree and fixes no cause. Owner direction of 2026-11-26: the devtools image installs the tools, and `PATH` gives each user of the container the intended versions.

## What Changes
- `devops repos worktrees add` starts no npm process. `install_node_tools` (`git/worktree_add.py`), its call in `commands/repos.py` and the message `worktrees_add_node_tools_failed` are deleted.
- CONTRIBUTING.md and docs/DEVCONTAINER_USAGE.md say where a worktree gets `openspec` from, and how to find a stale copy on `PATH`. docs/DESIGN.md says again that a worktree needs `npm ci --ignore-scripts` before `make design-tokens`.
- The command stops an install that a person can observe, so the change has a spec delta.

## Capabilities
- `repos-worktrees-add`: REMOVED requirement for the Node tools of the lock file; ADDED requirement that the command installs no Node tools.

## Impact
- A new worktree is made faster and is 87 MB smaller.
- In the devcontainer, `devops openspec check` in a new worktree runs the pinned `openspec` of the main checkout from `PATH`. A worktree needs `npm ci --ignore-scripts` only before `make design-tokens`, or when its branch changes `package-lock.json`.
- The change fits one pull request.

## Feasibility
- `OpenSpecTool.path` (`openspec/tool.py`) starts the binary of the checkout when it is there, else the `openspec` that `PATH` resolves.
- Proof in the devcontainer on 2026-11-26, after the stale links were removed: in a worktree with no `node_modules`, `uv run devops ci --check --only openspec` passes, and `which -a openspec` gives `node_modules/.bin/openspec` of the main checkout (2.2.0) before `/usr/local/bin/openspec` (2.1.1).
- `src/devops_cli` holds no code that writes `~/.local/share/devops-cli/tools/`.

## Existing Tool Considered
The devtools image and the `PATH` of the devcontainer already give each worktree the pinned tool. The change deletes code and adds none.
