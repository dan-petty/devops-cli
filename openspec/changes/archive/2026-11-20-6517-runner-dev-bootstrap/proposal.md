# Proposal: #6517

## Why

The runner image of the implement and fix-checks Jobs installs the whole dev group of `uv.lock` into `/app/.venv`, and `/app/.venv/bin` is first on PATH. So a check of a Job can run a dev tool of the image and not the one of the checkout that the agent changes, and the checkout gets its own venv only because the first `uv run` of the Job builds it. The owner direction of 2026-11-20 on #6517: the image holds no dev dependency, and one uv command builds the coder environment of the checkout.

## What Changes

- The `runner-deps` stage of `Dockerfile` installs only the runtime requirements of `uv.lock` with the `review` extra. The `lock` stage exports no `/lock/dev.txt`, and `runner-builder` syncs with `--no-dev`. The `runner` stage sets `UV_COMPILE_BYTECODE=0`, because the compile of all files was 71 s of the 110 s of a Job sync (#4814).
- `src/devops_cli/roadmap/runner_tools.py` gets `bootstrap_checkout`: `uv sync --group dev` online with `UV_HTTP_RETRIES=5`, or, when the uv-seed volume of #4814 is at `/opt/uv-seed` and its `seed.json` fits the uv version, the Python version and the `uv.lock` of the checkout, a copy of the seed cache into the uv cache and the same sync with `--offline` and `UV_MALWARE_CHECK=0`. The sync adds `--locked` for a new branch. A root `package-lock.json` adds `npm ci --ignore-scripts`. `checkout_environment` puts `node_modules/.bin` and the venv of the checkout first on PATH.
- The implement Job runs the bootstrap after its rebase and before it installs the hook environments, with `--locked` only for the new branch of a Planned item; a failure stops the item at the new step `bootstrap`. The fix-checks Job runs it without `--locked` at the start of the model fix, after tier 1, so tier 1 still repairs a stale `uv.lock`. The stage Job runs in the Service image, which holds no uv and no npm, so it runs no bootstrap until the stage Job moves to the runner image (#6417, #6528).
- The shell of the agent, the hooks, the scoped checks, the exit checks of a step, the project programs of the implement Job and the fixers of fix-checks get `checkout_environment`. No child that gets a token gets it.
- `RUNNER_TOOLS` names pytest, ruff, mypy, bandit, deptry, ast-grep, zizmor and pre-commit with the source `checkout`. `python -m devops_cli.roadmap.runner_tools` checks the tools of the image; with a checkout argument it runs the bootstrap and checks the tools of the venv of the checkout. The smoke step of `ci.yml` and `release.yml` runs both, then `uv run ruff --version`, `uv run pytest --version` and `uv run mypy --version` in the copy of the checkout.
- The runner image, the check module and the Jobs are observable, so the change carries a spec delta. The `lock` stage writes only `lock/runtime.txt`, so `container-image-layers` changes with it.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-runner`: The runner stage names its interpreter, The runner tools table names each tool that the gate and the hooks need, The runner image builds FROM the devtools image, The runner tool check fails on a missing tool, The smoke test of the runner image runs the tool check and bounds the size; added: A Job builds the coder environment of its checkout, A failed bootstrap ends the Job before its first agent step, The bootstrap uses the uv seed when it fits, The agent and the checks of a Job find the tools of the checkout first
- `container-image-layers`: The lock stage writes the requirements of the lock without the project, A change of the project keeps the dependency layers

## Impact

- Code: `src/devops_cli/roadmap/runner_tools.py`, `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/roadmap/implement/implement_hooks.py`, `src/devops_cli/roadmap/implement/implement_scoped_ci.py`, `src/devops_cli/roadmap/steps/fix_checks_repair.py`, `src/devops_cli/lang/en/messages.py`
- Image and workflows: `Dockerfile`, `.github/workflows/ci.yml`, `.github/workflows/release.yml`
- Documents: `docs/CLUSTER.md`, `docs/ROADMAP_WORKFLOW.md`
- Tests: `tests/roadmap/test_roadmap_runner_tools.py`, `tests/roadmap/implement/test_roadmap_implement_job_scoped.py`, `tests/roadmap/implement/test_roadmap_implement_step.py`, `tests/roadmap/implement/test_roadmap_implement_hooks.py`, `tests/roadmap/steps/test_roadmap_step_fix_checks_repair.py`
- Manifests: none. The image sets `UV_CACHE_DIR` on the home volume and `UV_COMPILE_BYTECODE=0`, and the uv-seed volume comes with #4814.

## Feasibility

- `uv help sync` of uv 0.13.9 (the uv of the devcontainer and of the devtools image) lists `--locked`, `--group` and `--offline`, and the uv binary holds `UV_MALWARE_CHECK` and the text "Set `UV_MALWARE_CHECK=0` to bypass this check". The process runner of the project starts each `uv` with `--preview-features malware-check,check-command`.
- Of the 7 other repositories of the Service, only `homelab` has a `uv.lock` (`devops gh api repos/dan-petty/<repo>/contents/uv.lock`), and its `pyproject.toml` has a `dev` group, so `--group dev` works in each checkout that the bootstrap syncs.
- `build_subprocess_env` in `src/devops_cli/core/process.py` resolves a program through the PATH of the child. A checkout folder on the PATH of the Job process would let the agent put a `git` there that gets the token, so only the agent and the check children get `checkout_environment`.
- `k8s/devops/cronjob-stage.yaml` runs the stage Job in `ghcr.io/dan-petty/devops-cli/service`, the smoke test of the Service image in `ci.yml` fails when `command -v uv` finds uv, and the admission policy admits only the Service image for a stage Job. So the stage Job cannot run the bootstrap, and this change gives it none.
- The decisions of the owner on #6517 and #4814 (2026-11-20) give the seed contract, the online retries, `UV_MALWARE_CHECK=0` on the seed path and `UV_COMPILE_BYTECODE=0`.

## Existing Tool Considered

uv (`uv sync --locked --group dev`, Apache-2.0 or MIT, maintained) builds the venv of the checkout from `uv.lock`, and npm (`npm ci`) installs the Node tools of `package-lock.json`. The change writes only the call order, the seed check and the PATH. It deletes the dev install of the image (the `/lock/dev.txt` export and its `uv pip install`) and the version check of a dev dependency against the image venv (`expected_text` of `DEV_GROUP`).
