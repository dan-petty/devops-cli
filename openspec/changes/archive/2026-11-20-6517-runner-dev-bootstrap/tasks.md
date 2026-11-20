# Tasks

## 1. The bootstrap and the tools of the checkout

Kind: behavior. Changes: `src/devops_cli/roadmap/runner_tools.py`, `src/devops_cli/lang/en/messages.py`.

- [x] 1.1 Write the failing tests in `tests/roadmap/test_roadmap_runner_tools.py`: the online sync and the npm install, the sync without `--locked` for an existing branch, the offline sync from a seed that fits, the online sync for a seed of another lock or uv, no command with no lock file, the error of a failed sync, the PATH of `checkout_environment`, the check of a tool of the checkout in its venv, and `main` with and without a checkout
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_runner_tools.py`
- [x] 1.2 Add `bootstrap_checkout` (with its `locked` flag), `checkout_environment`, `IMAGE_TOOLS` and `CHECKOUT_TOOLS`, move the dev tools to the source `checkout`, and give `main` the checkout argument
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_runner_tools.py`

## 2. The runner Jobs call the bootstrap and give the checks the tools of the checkout

Kind: behavior. Changes: `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/roadmap/implement/implement_hooks.py`, `src/devops_cli/roadmap/implement/implement_scoped_ci.py`, `src/devops_cli/roadmap/steps/fix_checks_repair.py`.

- [x] 2.1 Write the failing tests: the implement Job bootstraps the worktree before the hooks and the first model request, a stale lock of a staged branch locks again, a Planned item syncs with `--locked`, a failed bootstrap stops the item at `bootstrap`, the hooks and the scoped checks get the PATH of the checkout, the shell of the agent gets it, the fix-checks checkout opens on a stale lock and tier 1 locks it again, and the model fix bootstraps its worktree before the first model request and fails with the output of a failed sync
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job_scoped.py tests/roadmap/implement/test_roadmap_implement_step.py tests/roadmap/steps/test_roadmap_step_fix_checks_repair.py`
- [x] 2.2 Call `bootstrap_checkout` in the implement Job and the model fix of fix-checks, and pass `checkout_environment` to the agent shell and the check children
  - Verification: `$ uv run devops ci test tests/roadmap/implement tests/roadmap/steps/test_roadmap_step_fix_checks_repair.py`

## 3. The runner image and its smoke test

Kind: other (image and workflows). Changes: `Dockerfile`, `.github/workflows/ci.yml`, `.github/workflows/release.yml`.

- [x] 3.1 Remove the dev group from `runner-deps` and the `lock` stage, sync `runner-builder` with `--no-dev`, and set `UV_COMPILE_BYTECODE=0` in the `runner` stage
  - Verification: `$ ! git grep -n -e 'lock/dev.txt' -e 'only-dev' -- Dockerfile`
- [x] 3.2 Run the bootstrap check and `uv run ruff --version`, `uv run pytest --version` and `uv run mypy --version` on a copy of the checkout in the smoke step of `ci.yml` and `release.yml`, with the same text in both
  - Verification: `$ uv run devops ci --check --only actionlint,zizmor`
- [x] 3.3 Build `--target runner` with `podman-docker`, list `/app/.venv/bin` and run the changed smoke command of the checkout, and record the exit codes and the time of the bootstrap in a pull request comment

## 4. Documents

Kind: other (documents). Changes: `docs/CLUSTER.md`, `docs/ROADMAP_WORKFLOW.md`.

- [x] 4.1 State the image without the dev group, the bootstrap, the seed path, the PATH of the checks and the new smoke test
  - Verification: `$ uv run devops ci docs`
