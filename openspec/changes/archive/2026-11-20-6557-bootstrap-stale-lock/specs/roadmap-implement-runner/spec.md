## MODIFIED Requirements

### Requirement: A Job builds the coder environment of its checkout
The implement Job and the model fix of the fix-checks Job SHALL call `bootstrap_checkout` (`devops_cli.roadmap.runner_tools`) on their checkout before their first agent step. It SHALL run `uv sync --group dev` when `uv.lock` exists and an npm install when a root `package-lock.json` exists: `--locked` and `npm ci` on the new branch of a Planned item, else no `--locked` and `npm install`. A checkout with neither file SHALL get no command. Tier 1 of fix-checks SHALL run no bootstrap.

#### Scenario: The implement Job bootstraps before the hooks and the first model request
- **WHEN** the implement Job runs a staged item whose default branch holds `uv.lock` and `package-lock.json`
- **THEN** it runs `uv sync --group dev` and then `npm install --ignore-scripts` in the worktree, after the rebase, before `pre-commit install-hooks` and before the first model request

#### Scenario: A stale lock of a staged branch locks again
- **WHEN** the implement Job runs a staged item whose `uv.lock` does not match `pyproject.toml`
- **THEN** the only sync is `uv sync --group dev` with no `--locked`, and the item does not stop

#### Scenario: A Planned item syncs with its lock
- **WHEN** the implement Job runs a Planned item whose default branch holds `uv.lock`
- **THEN** the sync is `uv sync --locked --group dev`

#### Scenario: Tier 1 repairs a stale lock with no bootstrap
- **WHEN** the fix-checks checkout opens a branch whose `uv.lock` is stale and tier 1 gets a lockfile failure
- **THEN** the checkout opens, tier 1 runs `uv lock` and `uv lock --check`, and no sync runs

#### Scenario: The model fix bootstraps its worktree
- **WHEN** the fix-checks round reaches the model fix on a branch that holds `uv.lock`
- **THEN** it runs `uv sync --group dev` in the worktree before the first model request

### Requirement: The bootstrap uses the uv seed when it fits
`bootstrap_checkout` SHALL use the uv-seed volume `/opt/uv-seed` only when it holds `cache/` and a `seed.json` that names the uv version, the `<major>.<minor>` Python version of the Job and the sha256 of the checkout's `uv.lock`. Then it SHALL copy `cache/` into `UV_CACHE_DIR`, and a `--locked` sync SHALL run offline with `UV_MALWARE_CHECK=0`. Every other sync SHALL run online with `UV_HTTP_RETRIES=5` and `UV_MALWARE_CHECK=1`.

#### Scenario: No seed
- **WHEN** the bootstrap runs with no seed volume
- **THEN** it runs the online sync with `UV_HTTP_RETRIES=5` and `UV_MALWARE_CHECK=1`, and writes nothing into the uv cache

#### Scenario: A seed that fits
- **WHEN** the seed holds a cache entry and a `seed.json` that fits the uv, the Python and the `uv.lock` of the checkout
- **THEN** the cache entry is in `UV_CACHE_DIR`, and the last command is the offline sync with `UV_MALWARE_CHECK=0`

#### Scenario: A seed of another lock or another uv
- **WHEN** `seed.json` names another lock hash or another uv version
- **THEN** the bootstrap runs the online sync and copies nothing
