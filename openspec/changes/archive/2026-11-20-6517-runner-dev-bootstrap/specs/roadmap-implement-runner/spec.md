## MODIFIED Requirements

### Requirement: The runner stage names its interpreter
The `runner` stage SHALL set `UV_PYTHON` to the Python of the devtools image and `UV_PYTHON_DOWNLOADS` to `never`, and the shell of a step SHALL get `UV_PYTHON`. The `.python-version` of a checkout can name a patch release that the devtools image lacks, so `uv run` would find no interpreter.

#### Scenario: uv finds an interpreter
- **WHEN** CI runs the bootstrap of a Job and then `uv run ruff --version` in a copy of the checkout, in the runner image with a read-only root, a tmpfs home, no capability and no new privileges
- **THEN** the command prints the ruff version of `uv.lock` and exits 0

### Requirement: The runner tools table names each tool that the gate and the hooks need
`RUNNER_TOOLS` in `devops_cli.roadmap.runner_tools` SHALL list each program that a runner Job needs, its source (the base system, the devtools image, the project or the venv of the checkout), why it is there, and the command that proves it runs. `NOT_IN_RUNNER` SHALL name each program that a step of the Job does not count on, with the reason. The module SHALL hold no tool version: the devtools image and `uv.lock` give them.

#### Scenario: A source of the gate needs a program that is in neither table
- **WHEN** a program of a `devops ci` row, of a hook of `.pre-commit-config.yaml`, of a required job of `ci.yml` or of a live-marked test is in neither `RUNNER_TOOLS` nor `NOT_IN_RUNNER`
- **THEN** a test fails and names the program

#### Scenario: A Dockerfile pin bump changes no runner code
- **WHEN** a pull request moves the tag and the digest of the devtools image in `Dockerfile`
- **THEN** it changes no line of `src/devops_cli/roadmap/runner_tools.py`, because `RUNNER_TOOLS` holds no version

### Requirement: The runner image builds FROM the devtools image
The `runner` stage SHALL build from `runner-deps`, which builds FROM the devtools image, pinned by tag and digest. `runner-deps` SHALL add the user `devops` (uid and gid 1000) and install only the runtime requirements of the `lock` stage, with the `review` extra, into `/app/.venv`. The devtools image SHALL give each image tool of `RUNNER_TOOLS`. The image SHALL run as user 1000 with `ENTRYPOINT ["devops"]`, `/app/.venv/bin` first on `PATH` and `UV_COMPILE_BYTECODE=0`.

#### Scenario: The image is built and started
- **WHEN** a person builds `--target runner` and runs `docker run --rm --entrypoint id <image> -u` and `docker run --rm <image> --version`
- **THEN** the build exits 0, the first command prints `1000`, and the second prints the version of devops-cli

#### Scenario: The image venv holds no dev tool
- **WHEN** a person runs `docker run --rm --entrypoint sh <runner image> -c 'ls /app/.venv/bin'`
- **THEN** the output lists no `ruff`, `mypy`, `pytest` or `pre-commit`

### Requirement: The runner tool check fails on a missing tool
The smoke test of the runner image SHALL run `python -m devops_cli.roadmap.runner_tools` as user 1000 on the loaded image, which checks each image tool, and with a copy of the checkout as its argument, which runs the bootstrap and checks each tool of the checkout. The check SHALL fail when an image program is not on PATH, a checkout program is not in `<checkout>/.venv/bin`, a version command fails, the project prints another version, or the bootstrap fails. It SHALL compare no other version.

#### Scenario: A tool is missing or at another version
- **WHEN** a program of the image is not on PATH, its version command exits non-zero, or the project prints a version other than the version of its installed distribution
- **THEN** the check names the tool and exits 1

#### Scenario: A tool of the devtools image prints any version
- **WHEN** the version command of a tool that the devtools image gives exits 0
- **THEN** the check of the tool passes, and the check runs only that version command

#### Scenario: Every tool passes
- **WHEN** every version command of an image tool exits 0, and the project prints its installed version
- **THEN** the check prints the number of image tools, runs no version command of a tool of the checkout, and exits 0

#### Scenario: A tool of the checkout is missing from its venv
- **WHEN** the check runs with a checkout whose `.venv/bin` lacks `ruff`
- **THEN** the check names `ruff` and the checkout and exits 1

#### Scenario: The check of a checkout runs its bootstrap first
- **WHEN** the check runs with a checkout that holds `uv.lock`
- **THEN** it runs `uv sync --locked --group dev` in the checkout, then the version command of each tool of the checkout there, and exits 1 with the output of the sync when the sync fails

### Requirement: The smoke test of the runner image runs the tool check and bounds the size
The smoke test of the runner image in `ci.yml` and in `release.yml` SHALL be the same text, SHALL run the tool check of the image and the tool check of a copy of the checkout, SHALL then run `uv run ruff --version`, `uv run pytest --version` and `uv run mypy --version` in that copy, and SHALL fail when the image is larger than 7000000000 bytes.

#### Scenario: The smoke test runs on the loaded image
- **WHEN** the Runner Image job of `ci.yml` runs its smoke test on the loaded image
- **THEN** the check module prints that every runner tool is on PATH and runs, for the image and for the checkout, the three `uv run` commands exit 0, and the step fails when `docker image inspect` reports more than 7000000000 bytes

## ADDED Requirements

### Requirement: A Job builds the coder environment of its checkout
Each stage, implement and fix-checks Job SHALL call `bootstrap_checkout` of `devops_cli.roadmap.runner_tools` with its checkout before its first agent step. The function SHALL run `uv sync --locked --group dev` in a checkout that holds `uv.lock`, and `npm ci --ignore-scripts` in a checkout that holds a root `package-lock.json`. A checkout with neither file SHALL get no command.

#### Scenario: The implement Job bootstraps before the hooks and the first model request
- **WHEN** the implement Job runs an item whose default branch holds `uv.lock` and `package-lock.json`
- **THEN** it runs `uv sync --locked --group dev` and then `npm ci --ignore-scripts` in the worktree, after the rebase, before `pre-commit install-hooks` and before the first model request

#### Scenario: The fix-checks checkout bootstraps its worktree
- **WHEN** the fix-checks checkout opens the head branch of a pull request that holds `uv.lock`
- **THEN** the sync ran in the worktree before the block of the checkout starts

### Requirement: A failed bootstrap ends the Job before its first agent step
A bootstrap command that exits non-zero or runs out of time SHALL raise `ToolExecutionError` with the command and its output. The implement Job SHALL stop the item at the step `bootstrap` with nothing to push, the stage Job SHALL end as an infrastructure failure, and the fix-checks round SHALL end with the error.

#### Scenario: A failed bootstrap stops the implement item
- **WHEN** the sync of the implement Job exits 2
- **THEN** the item stops at the step `bootstrap` with no model request and no push, and the comment holds the output of the sync

#### Scenario: A failed bootstrap ends the stage Job
- **WHEN** the stage Job runs on a clone that holds `uv.lock` and the sync fails
- **THEN** the sync ran in the clone, no model request was made, and the Job ends as evicted with the class `ci_infra`

### Requirement: The bootstrap uses the uv seed when it fits
`bootstrap_checkout` SHALL use the uv-seed volume at `/opt/uv-seed` only when it holds `cache/` and a `seed.json` whose `uv`, `python` and `uv_lock_sha256` equal the uv version, the `<major>.<minor>` Python version of the Job and the sha256 of the `uv.lock` of the checkout. Then it SHALL copy `cache/` into `UV_CACHE_DIR` and sync offline with `UV_MALWARE_CHECK=0`. Else it SHALL sync online with `UV_HTTP_RETRIES=5` and `UV_MALWARE_CHECK=1`.

#### Scenario: No seed
- **WHEN** the bootstrap runs with no seed volume
- **THEN** it runs the online sync with `UV_HTTP_RETRIES=5` and `UV_MALWARE_CHECK=1`, and writes nothing into the uv cache

#### Scenario: A seed that fits
- **WHEN** the seed holds a cache entry and a `seed.json` that fits the uv, the Python and the `uv.lock` of the checkout
- **THEN** the cache entry is in `UV_CACHE_DIR`, and the last command is the offline sync with `UV_MALWARE_CHECK=0`

#### Scenario: A seed of another lock or another uv
- **WHEN** `seed.json` names another lock hash or another uv version
- **THEN** the bootstrap runs the online sync and copies nothing

### Requirement: The agent and the checks of a Job find the tools of the checkout first
The shell of the agent of a step, the `pre-commit` runs, the scoped checks, the exit checks of a step, the project programs of the implement Job and the tier-1 commands of fix-checks SHALL get a PATH that starts with `<checkout>/node_modules/.bin` and `<checkout>/.venv/bin`, then the PATH of the Job process. The Job process and each child that gets a token SHALL keep the PATH of the image.

#### Scenario: The checks of the implement Job
- **WHEN** the implement Job runs the `pre-commit` stage, the `pre-push` stage and the static scoped check
- **THEN** the PATH of each child starts with `node_modules/.bin` and `.venv/bin` of the worktree

#### Scenario: The shell of the agent
- **WHEN** a step builds the shell of its agent for a checkout
- **THEN** the PATH of the shell starts with `node_modules/.bin` and `.venv/bin` of that checkout
