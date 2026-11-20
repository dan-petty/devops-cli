# Design

## Decisions

- **One function, `bootstrap_checkout` in `src/devops_cli/roadmap/runner_tools.py`, builds the coder environment, and the implement Job and the model fix of fix-checks call it with their checkout.**: The module holds the tool inventory, so one place owns the tools and the way a Job gets them. Copies of the commands could drift.
- **The stage Job runs no bootstrap.**: `k8s/devops/cronjob-stage.yaml` runs it in the Service image, which holds no uv and no npm (the smoke test of the Service image in `ci.yml` fails when `command -v uv` finds uv), and the admission policy admits only that image for a stage Job. A bootstrap there would exit 127 on every repository with `uv.lock`, and the Job would end as `ci_infra` and run again each hour. The stage part waits for the move of the stage Job to the runner image (#6417, #6528); no code checks whether uv is present.
- **`--locked` only for the new branch of a Planned item.**: That branch starts at the fetched default branch, whose `uv.lock` CI keeps current, so the owner's `uv sync --locked --group dev` holds. A staged branch and the head branch of fix-checks exist, and their `uv.lock` can be stale. Before this change the first `uv run` of the Job (`pre-commit install-hooks`) locked again and the Job went on; a `--locked` sync would stop the item as `ci_infra` instead. The sync without `--locked` keeps that behavior and adds no retry, cap or failure class.
- **The fix-checks Job bootstraps at the start of the model fix, not in the checkout.**: Tier 1 repairs a check that failed on a stale `uv.lock` (`uv lock`, `uv lock --check`), and a `--locked` sync before it would fail that case first. Tier 1 runs only `uv run` and `uv lock`, which build what they need. A failed bootstrap of the model fix ends the round as failed with the output, as a failed hook install does.
- **The bootstrap runs only standard commands: `uv sync --group dev` (with `--locked` on a new branch) and `npm ci --ignore-scripts`.**: The devcontainer post-create step runs the same sync, and `npm ci` refuses a lock that does not match `package.json`. A checkout with no `uv.lock` gets no sync and a checkout with no root `package-lock.json` gets no npm install, so a repository of another toolchain starts as before.
- **The seed path is a presence check, not a gate.**: The bootstrap uses `/opt/uv-seed` only when `cache/` and `seed.json` are there and `seed.json` holds `uv`, `python` (`<major>.<minor>`) and `uv_lock_sha256` equal to the uv of the Job, its Python and the sha256 of the `uv.lock` of the checkout. Else it syncs online. A uv of another version can keep its cache in another layout, and the cached wheels are for one Python minor version, so the lock hash alone is not enough. The Job never needs the seed to start (#4814).
- **The seed copy goes into `UV_CACHE_DIR` on the home volume with `shutil.copytree`.**: uv needs a writable cache even with `--offline` (#4814), and the clone's `.venv` is on the same volume.
- **`UV_COMPILE_BYTECODE=0` in the `runner` stage only.**: The build stages keep `1`, so the image venv stays compiled. The sync of a checkout compiled 19212 files in 71 s of 110 s (#4814), and Python compiles each module that a check imports.
- **`checkout_environment` goes to the agent shell and to the check children only.**: `run_subprocess` resolves `git` and `gh` through the PATH of the child, and the agent can write `node_modules/.bin` and `.venv/bin`. The Job process keeps the PATH of the image, so a token child never runs a program of the checkout.
- **The children that get the PATH: the agent shell, `pre-commit` (hooks), the scoped checks, the exit checks and verification commands of a step, the test-form collection, the project programs of the implement Job (`docs generate`, the archive) and the tier-1 fixers and checks of fix-checks.**: Each of them can start `devops`, `openspec` or a dev tool. `uv run` already puts the checkout venv first; the PATH adds the Node tools. The strength check runs only `uv run` Python tools, so it keeps the environment of `uv run`.
- **A failed bootstrap raises `ToolExecutionError`.**: Its failure class is `ci_infra`. The implement Job stops the item at the new step `bootstrap` with nothing to push, as a failed hook install does. The model fix of fix-checks returns the error as its reason, as a failed hook install does there.
- **The tools of the checkout keep their place in `RUNNER_TOOLS` with the source `checkout`.**: The tests that hold each program of the gate to the tables stay as they are. The check of a checkout tool requires the program in `<checkout>/.venv/bin` and runs its version command there; `uv.lock` gives its version, so the check compares none.

## Rejected alternatives

- **Put the checkout folders first on the PATH of the Job process.**: `build_subprocess_env` passes the PATH of the process to every child, and a `git` child with the token resolves `git` through it. An agent could then write `.venv/bin/git` and get the token.
- **Keep the dev group in the image and only add the bootstrap.**: The owner direction of 2026-11-20 removes the dev group from the image, and a check could still run the image tool.
- **Copy the commands into each Job.**: Two copies of the seed check and the commands could drift.
- **Bootstrap the stage Job only when uv is on PATH.**: That check would be compensating code for an image that does not fit the item; the stage Job moves to the runner image instead (#6417, #6528).
- **Bootstrap the fix-checks worktree when the checkout opens.**: The review of the first version found that a `--locked` sync there fails a stale lock before tier 1 can repair it, and the Job exits 1 for that head.
- **Sync with `--locked` on every branch.**: A staged branch with a stale `uv.lock` would stop at `bootstrap` as `ci_infra`, where the `uv run` of the hook install locked again before.
- **Run the bootstrap in the image entrypoint.**: The checkout does not exist when the pod starts.
- **Compare only the lock hash of the seed.**: A seed of another uv or another Python minor version would make the offline sync fail with a missing cache entry and stop the Job.
- **Use `pip install -e .[dev]`.**: It adds a second resolver and does not read `uv.lock`.

## Workflow follow-up

- #4814 builds the uv-seed image volume to the `seed.json` contract of this change and mounts it in the runner Job.
- #6409 adds the root `package-lock.json`; from then on the bootstrap installs the pinned OpenSpec. The stage Job runs no bootstrap until it moves to the runner image (#6417, #6528).
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
