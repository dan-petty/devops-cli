# Design

## Decisions

- **The sources are probes.** The uv and npm pages name the settings, and a probe with uv 0.13.6, npm 11.19.1 and node 24.22.2 confirms each refused key (proposal, Feasibility). The constant claims only the keys that a probe ran.
- **The names sit in the existing tuple, in a block of their own,** after the block of #2672. The npm settings are exact names, not `NPM_CONFIG_*`, because `install_tools.py` sets other `npm_config_` keys. The three npm names that have two words after the prefix use `[_-]`, because npm reads `npm_config_script-shell` as the same setting as `npm_config_script_shell` (probe). The match is on the upper-case key, so the case of the key does not matter.
- **`UV_PYTHON` and `UV_PYTHON_INSTALL_DIR` are refused from a caller and still reach an isolated child from the environment.** #1735 added the prefix `UV_` because the gate's `uv run` on a GitHub runner lost `UV_PYTHON`, `UV_CACHE_DIR` and `UV_PYTHON_INSTALL_DIR`: it removed the environment that `uv sync` had built, downloaded CPython and every wheel again, and ran 221 installs again. A build or check that averages more than 5 minutes is a P0 bug, so the prefix stays. `tests/test_subprocess_env_boundary.py` pins the behavior. The environment of the person is as trusted as `PATH`, which also decides what a child starts. A caller override is different: a caller gives a value that code of devops-cli or its input chose. The requirement "An isolated child gets no refused key from the environment" names this exception.
- **`UV_PROJECT_ENVIRONMENT` does not reach an isolated child.** Nothing in the repository sets it: `ci.yml`, the toolchain action and the `Dockerfile` do not, and a probe showed that uv starts the `bin/python` of the environment that it names. The `UV_` prefix would pass it, so the key joins `DEFAULT_DENIED_ENV_PATTERNS`, which applies to the ambient environment only. Not even `extra_allowed_keys` passes it: a denied key stays out.
- **`npm_config_shell`, `npm_config_python` and `PYTHON` are refused.** The probes ran the marker (proposal, Feasibility). `devops install-tools` runs `npm ci`, which can build a native package through node-gyp, and no caller sets these keys.
- **`VIRTUAL_ENV` leaves the allowlist.** No child needs it. `uv run` uses the project environment and ignores the key unless `--active` is given, and no `uv` call of `src/` or of the workflows gives `--active`. `install_tools` names its interpreter with `-p`. The key was in the first allowlist (v0.2.12) with no recorded reason. The invariant "The ambient allowlist holds no refused key" also needs it: a key that the guard refuses cannot be on the allowlist. A person who needs the key for one child names it in `extra_allowed_keys`.
- **`npm_config_userconfig` and `npm_config_globalconfig` are accepted.** `install_tools.py` sets both, and the key names a file that the caller controls. A probe showed that an npmrc with `script-shell` starts a program, as a `gh` configuration directory can (#2672). `UV_CONFIG_FILE` is accepted for the same reason: a `uv.toml` with `[pip] python` starts a program (probe). The same rule applies as in #2483 for `HOME` and `XDG_CONFIG_HOME`: a caller that takes the path from an untrusted source must check it first.
- **No npm key reaches an isolated child from the environment.** The allowlist holds no `npm_config_` key, so each refused npm key stays out already. The tests pin it.
- **The spec change adds requirements and modifies one.** The modified requirement lists the keys that an isolated child never gets. Its text names the exception of `UV_PYTHON` and `UV_PYTHON_INSTALL_DIR`, and its one scenario is edited to match.

## Rejected alternatives

- **Remove the prefix `UV_` from the allowlist.** It breaks `UV_CACHE_DIR`, `UV_LINK_MODE` and `UV_MALWARE_CHECK`, and the runner keys of #1735 (the gate's `uv run` rebuilds its environment).
- **Drop `UV_PYTHON` from the environment, as the issue asks.** It brings back the rebuild of #1735 on each CI runner, and CI speed is P0.
- **Drop `UV_PYTHON` and `UV_PYTHON_INSTALL_DIR` from the environment and add them to `extra_allowed_keys` at each call.** The gate starts `uv run` from many call sites in `commands/ci.py`, `ci/cache.py`, `ci/fail_to_pass.py` and `ci/mutate.py`. Each one would need the grant, and a missed one brings back the slow rebuild of #1735.
- **Check the value of the key.** A version request (`3.14`) and a path are both valid, and a check that tells them apart is a new hand-written helper.
- **Refuse the whole `npm_config_` family.** It breaks the five keys that `install_tools.py` sets.
- **Keep `VIRTUAL_ENV` in the allowlist and refuse it only from a caller.** The invariant test and the spec say that an allowlist key is never refused, and no child needs the key.

## Keys considered and not claimed

- `GOFLAGS` (`-toolexec`): the page of `go help build` names the flag, but `go` is not installed here, so no probe ran.
- `npm_config_browser` and `npm_config_node_gyp`: the probes ran no marker.

## Non-goals

- The keys of #2674 (secrets and log files), `LESS` (#2735) and `GH_TELEMETRY_ENDPOINT_URL` (#2739).
