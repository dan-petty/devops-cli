# Proposal

## Why

In a new worktree the `openspec` row of `devops ci` fails until a person runs `npm ci --ignore-scripts`, because the gate runs the older `openspec` of the image when the worktree holds no `node_modules` (#7233).

## What Changes

- Add `install_node_tools` beside `src/devops_cli/git/worktree_add.py:def add_worktree`: it runs `npm ci --ignore-scripts` in a worktree that holds `package-lock.json`, starts no process without that file, and returns a warning text when the run fails.
- Call the helper from `src/devops_cli/commands/repos.py:def worktrees_add` on the new worktree when the run is no dry run, and print a returned text with `print_warning`.
- Add the message `worktrees_add_node_tools_failed` beside `src/devops_cli/lang/en/messages.py:656:worktrees_add_created: str = "Created worktree {path} on branch {branch}."`, so the warning names `npm ci --ignore-scripts`, the worktree path and the exit code.
- Add three tests to `tests/core/test_repos_worktrees_add.py`: the lock file present, no lock file, and a failed install that keeps the worktree.
- Update `CONTRIBUTING.md`, `docs/DESIGN.md` and `docs/DEVCONTAINER_USAGE.md`, and regenerate `docs/commands/repos.md`, so each says that the command installs the pinned Node tools.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `repos-worktrees-add`: A new worktree gets the Node tools of the lock file

## Impact

- Code: `src/devops_cli/git/worktree_add.py`, `src/devops_cli/commands/repos.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `CONTRIBUTING.md`, `docs/DESIGN.md`, `docs/DEVCONTAINER_USAGE.md`, `docs/commands/repos.md`
- Tests: `tests/core/test_repos_worktrees_add.py`

## Feasibility

- The `probes` input gives, word for word, "The path `package-lock.json` is a file of the staging commit." and "The path `src/devops_cli/openspec/gate.py` is a file of the staging commit.", so the lock file and the gate module that the issue cites are both at the staged commit.
- The gate compares the printed version with the locked one: `src/devops_cli/openspec/gate.py:def version_finding` reads the version of the lock file with `locked_version`, and `src/devops_cli/openspec/tool.py:def locked_version` reads the version that `package-lock.json` pins.
- The tool of a checkout is the binary under `node_modules/.bin` when it exists: `src/devops_cli/openspec/tool.py:def installed_program` returns that path under the root, and `src/devops_cli/openspec/tool.py:class OpenSpecTool` runs it. A new worktree holds no `node_modules`, so the older `openspec` of the image on PATH runs and the version finding of the issue appears.
- The command starts four git commands and no npm command: `src/devops_cli/git/worktree_add.py:def _commands` builds them, `src/devops_cli/git/worktree_add.py:def add_worktree` runs them, and `src/devops_cli/commands/repos.py:def worktrees_add` calls `add_worktree` and then claims the issue.
- A missing program is no exception: `src/devops_cli/git/worktree_add.py:def _run` calls `run_subprocess` with `check=False`, and `src/devops_cli/core/process.py:def run_subprocess` answers a missing program with `CONST_EXIT_COMMAND_NOT_FOUND`, so a missing `npm` becomes a warning.
- The staged values are `CONST_NPM_LOCKFILE` with the value `package-lock.json`, at `src/devops_cli/config/constants.py:226:CONST_NPM_LOCKFILE: Final[str] = "package-lock.json"`, and `BIN_NPM` with the value `npm`, at `src/devops_cli/config/commands.py:38:BIN_NPM: str = "npm"`.
- `read_file` on `src/devops_cli/lang/en/messages.py` shows the worktree add messages in one block, `src/devops_cli/lang/en/messages.py:class RepoMessages`, where `worktrees_add_created` sits at `src/devops_cli/lang/en/messages.py:656:worktrees_add_created: str = "Created worktree {path} on branch {branch}."`, so the new warning goes beside it.
- The command writes its warnings with `print_warning` and `prefix=False`, as `src/devops_cli/commands/repos.py:def _render_claim` shows, and `src/devops_cli/output/console.py:def print_warning` takes that keyword.
- The new tests go in `tests/core/test_repos_worktrees_add.py:def _add`; the repository is real and its origin is a bare repository in `tmp_path`, as `tests/core/test_repos_worktrees_add.py:def repo` shows, so git runs offline.
- The process fake installs for every child and records each call, at `tests/support/fakes/process.py:def process_fake`, and `ProcessFake.answer` takes a matcher and a `ProcessAnswer`; git runs for real through `tests/support/implement_step.py:def git_for_real`.
- The install that the plan does not call is `src/devops_cli/roadmap/runner_tools.py:def bootstrap_checkout`, which builds the whole coder environment, the `uv sync` included, and raises on a failure.
- The manual step that the issue removes is in `CONTRIBUTING.md:63:Run `npm ci --ignore-scripts` again in each new worktree and after each change of `package-lock.json`.` (the sentence around it), in `docs/DESIGN.md:45:In a new worktree or on another host, run:` and in `docs/DEVCONTAINER_USAGE.md:42:In a new worktree, run `npm ci --ignore-scripts` before `devops openspec check` or `make design-tokens`.`, where each tells a person to run the install in a new worktree.
- The helper calls `run_subprocess` with the new worktree as `cwd`, so it needs a checkout of that worktree and a network to the npm registry; the three new tests answer `npm` with the process fake, so they need neither.
- The command needs a checkout of the repository, because `add_worktree` runs git; the test repository is real and its origin is a bare repository in `tmp_path`, so git runs offline through `git_for_real`.
- The docs generation `uv run devops docs generate` needs a checkout of the repository, because it reads the commands and writes the generated page.
- The verify `uv run devops ci test tests/core/test_repos_worktrees_add.py` runs the failure class `test`; it needs the runner tools `uv`, `python`, `devops` and `git` of the image tool list, `npm` is answered by the fake, and the pod setting `readOnlyRootFilesystem: true` holds because the tests write only under the pytest temporary directory.
- The verify `uv run devops ci docs` runs the failure class `test`; it needs the runner tools `uv`, `python` and `devops` of the image tool list, and it reads the repository and reaches no network.
- The plan introduces no program of its own: both verifies are existing rows of `devops ci`, so no failure class, no runner capability and no pod setting is new, and `npm` of the image tool list serves only the real-system check.
- First checks on the real system: `uv run devops repos worktrees add 7233 --type fix --slug node-tools` in a clone that holds `package-lock.json`, then `test -x .data/agent/worktrees/w-7233/node_modules/.bin/openspec`, then `uv run devops ci --check --only openspec` in that worktree; the first command needs a network to the npm registry.

## Existing Tool Considered

npm/cli, which the repository already uses: `CONTRIBUTING.md` records the install step for a new worktree, and `package-lock.json` pins `@fission-ai/openspec` 2.2.0 and `style-dictionary` 5.8.0. `npm ci` installs exactly the versions of the lock file, and `--ignore-scripts` runs no lifecycle script, so the change adds one call of it and builds no tool.

## Dependencies

None.
