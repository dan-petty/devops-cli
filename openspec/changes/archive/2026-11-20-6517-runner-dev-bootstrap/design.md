# Design

## Decisions

- **One function, `bootstrap_checkout` in `src/devops_cli/roadmap/runner_tools.py`, builds the coder environment, and the three Jobs call it with their checkout.**: The module holds the tool inventory, so one place owns the tools and the way a Job gets them. Three copies of the commands could drift.
- **The bootstrap runs only standard commands: `uv sync --locked --group dev` and `npm ci --ignore-scripts`.**: The devcontainer post-create step runs the same sync, and `npm ci` refuses a lock that does not match `package.json`. A checkout with no `uv.lock` gets no sync and a checkout with no root `package-lock.json` gets no npm install, so a repository of another toolchain starts as before.
- **The seed path is a presence check, not a gate.**: The bootstrap uses `/opt/uv-seed` only when `cache/` and `seed.json` are there and `seed.json` holds `uv`, `python` (`<major>.<minor>`) and `uv_lock_sha256` equal to the uv of the Job, its Python and the sha256 of the `uv.lock` of the checkout. Else it syncs online. A uv of another version can keep its cache in another layout, and the cached wheels are for one Python minor version, so the lock hash alone is not enough. The Job never needs the seed to start (#4814).
- **The seed copy goes into `UV_CACHE_DIR` on the home volume with `shutil.copytree`.**: uv needs a writable cache even with `--offline` (#4814), and the clone's `.venv` is on the same volume.
- **`UV_COMPILE_BYTECODE=0` in the `runner` stage only.**: The build stages keep `1`, so the image venv stays compiled. The sync of a checkout compiled 19212 files in 71 s of 110 s (#4814), and Python compiles each module that a check imports.
- **`checkout_environment` goes to the agent shell and to the check children only.**: `run_subprocess` resolves `git` and `gh` through the PATH of the child, and the agent can write `node_modules/.bin` and `.venv/bin`. The Job process keeps the PATH of the image, so a token child never runs a program of the checkout.
- **The children that get the PATH: the agent shell, `pre-commit` (hooks), the scoped checks, the exit checks and verification commands of a step, the test-form collection, the project programs of the implement Job (`docs generate`, the archive) and the tier-1 fixers and checks of fix-checks.**: Each of them can start `devops`, `openspec` or a dev tool. `uv run` already puts the checkout venv first; the PATH adds the Node tools. The strength check runs only `uv run` Python tools, so it keeps the environment of `uv run`.
- **A failed bootstrap raises `ToolExecutionError`.**: Its failure class is `ci_infra`. The implement Job stops the item at the new step `bootstrap` with nothing to push, as a failed hook install does. The stage Job reads it as an infrastructure failure and ends as evicted. The fix-checks command prints the error and exits 1, as for a checkout that it cannot open.
- **The tools of the checkout keep their place in `RUNNER_TOOLS` with the source `checkout`.**: The tests that hold each program of the gate to the tables stay as they are. The check of a checkout tool requires the program in `<checkout>/.venv/bin` and runs its version command there; `uv.lock` gives its version, so the check compares none.

## Rejected alternatives

- **Put the checkout folders first on the PATH of the Job process.**: `build_subprocess_env` passes the PATH of the process to every child, and a `git` child with the token resolves `git` through it. An agent could then write `.venv/bin/git` and get the token.
- **Keep the dev group in the image and only add the bootstrap.**: The owner direction of 2026-11-20 removes the dev group from the image, and a check could still run the image tool.
- **Copy the commands into each Job.**: Three copies of the seed check and the commands could drift.
- **Run the bootstrap in the image entrypoint.**: The checkout does not exist when the pod starts.
- **Compare only the lock hash of the seed.**: A seed of another uv or another Python minor version would make the offline sync fail with a missing cache entry and stop the Job.
- **Use `pip install -e .[dev]`.**: It adds a second resolver and does not read `uv.lock`.

## Workflow follow-up

- #4814 builds the uv-seed image volume to the `seed.json` contract of this change and mounts it in the runner Job.
- #6409 adds the root `package-lock.json`; from then on the bootstrap installs the pinned OpenSpec. The OpenSpec calls that the stage Job makes in its own process keep the OpenSpec of the image until `version_finding` of #6409 decides.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
