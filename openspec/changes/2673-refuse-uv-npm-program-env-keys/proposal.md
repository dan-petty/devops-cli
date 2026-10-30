# Proposal

## Why

Issue #2673: the subprocess environment guard accepts the uv and npm keys that make a child run a program.

- `build_subprocess_env` in `src/devops_cli/core/process.py` refuses a caller override that `CONST_CODE_LOADING_ENV_PATTERNS` matches. The patterns hold no key of `uv` or `npm`. #2503 and #2672 left these keys open because no probe of them had run.
- `UV_PYTHON` names the interpreter that `uv run` starts. `VIRTUAL_ENV` and `UV_PROJECT_ENVIRONMENT` name an environment whose `bin/python` uv starts. `UV_PYTHON_INSTALL_DIR` names a directory of interpreters that uv starts when it prefers its own Python builds.
- npm starts the shell of `script-shell` for each script, and `node-options` becomes `NODE_OPTIONS` for each script. npm starts the program of `git` for a git dependency and the program of `editor` for `npm config edit`, and it loads the module of `init-module` for `npm init`.
- `VIRTUAL_ENV` is in `DEFAULT_ALLOWED_ENV_VARS`, so an isolated child also gets it from the environment. The prefix `UV_` is in `DEFAULT_ALLOWED_ENV_PREFIXES` (#1735), so an isolated child also gets each `UV_` key from the environment.
- `src/devops_cli/commands/install_tools.py` sets `npm_config_cache`, `npm_config_userconfig`, `npm_config_globalconfig`, `npm_config_update_notifier` and `npm_config_loglevel` as caller overrides, so a pattern for the whole `npm_config_` family cannot work.

## What Changes

- The guard refuses `UV_PYTHON`, `UV_PYTHON_INSTALL_DIR`, `UV_PROJECT_ENVIRONMENT`, `VIRTUAL_ENV`, `npm_config_script_shell`, `npm_config_node_options`, `npm_config_git`, `npm_config_editor` and `npm_config_init_module` as a caller override. The npm names also match the spelling with a hyphen, which npm reads as the same setting. Each raises the same `SecurityError` as the other refused keys, with isolation on and off.
- `VIRTUAL_ENV` leaves `DEFAULT_ALLOWED_ENV_VARS`, so an isolated child no longer gets it. No child of devops-cli reads it (Feasibility).
- The prefix `UV_` stays. An isolated child still gets the uv settings of the person, `UV_PYTHON` and `UV_PYTHON_INSTALL_DIR` included, because the gate on a CI runner needs them (#1735). The design gives the evidence.
- The guard keeps accepting `npm_config_userconfig`, `npm_config_globalconfig`, `UV_CONFIG_FILE` and the keys that name no program. The design gives the reason.
- `ARCHITECTURE.md` names the new refused keys. The refusal is what a consumer sees, so the change adds requirements to the `subprocess-environment` spec and modifies the one requirement that lists the keys an isolated child never gets.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `subprocess-environment`: the guard refuses the keys of uv and npm that name a program, and an isolated child gets no `VIRTUAL_ENV`. The requirement "An isolated child gets no refused key from the environment" names the `UV_` exception.

## Impact

- Code: `src/devops_cli/config/constants.py` (one new block of `CONST_CODE_LOADING_ENV_PATTERNS`), `src/devops_cli/core/process.py` (`VIRTUAL_ENV` leaves the allowlist).
- Tests: `tests/test_subprocess_env_uv_npm.py`, and `tests/test_subprocess_env_boundary.py` (the three lines that expect `VIRTUAL_ENV`).
- Documents: `ARCHITECTURE.md`, and the Purpose of `openspec/specs/subprocess-environment/spec.md` (edited by hand when the change is archived).

## Feasibility

The guard accepts the keys today. On `origin/main` at `ad0bdf1f`, `build_subprocess_env(env={"UV_PYTHON": "x", "npm_config_script_shell": "x"})` returns both keys with no `SecurityError`.

Each probe ran with uv 0.13.6, npm 11.19.1 and node 24.22.2 on Linux. It used `env -i`, a temporary `HOME`, `PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring`, `--offline` for uv, and a marker program that appends a line to a file and then runs the real program or exits. No probe opened a network connection or started a long-running process. Each probe had a control run with the key unset, and the control wrote no marker.

- `UV_PYTHON`: `uv run --no-project --offline python -c pass` ran the marker.
- `VIRTUAL_ENV`: `uv --offline --no-config pip list` ran the `bin/python` of the named environment.
- `UV_PROJECT_ENVIRONMENT`: `uv run --offline python -c pass` in a project ran the `bin/python` of the named environment.
- `UV_PYTHON_INSTALL_DIR`: with `UV_MANAGED_PYTHON=1` and a fake `cpython-<version>-linux-x86_64-gnu/bin/python3.14` below the directory, `uv run --no-project --offline python -c pass` ran the marker. Without `UV_MANAGED_PYTHON`, uv chose another interpreter and ran no marker. CI sets `UV_MANAGED_PYTHON=1`.
- `UV_CONFIG_FILE`: a `uv.toml` with `[pip] python = "<marker>"` and `uv pip list --offline` ran the marker.
- `npm_config_script_shell`: `npm run t` ran the marker as the shell. The spellings `npm_config_script-shell` and `NPM_CONFIG_SCRIPT_SHELL` ran it too.
- `npm_config_node_options`: a script `node -e 0` loaded `--require=<module>` from the key. The spelling `npm_config_node-options` did the same.
- `npm_config_git`: `npm install --offline git+ssh://git@127.0.0.1:1/x/y.git` started the program of the key (`ls-remote`). The program was a marker that exits 1.
- `npm_config_editor`: `npm config edit` started the program of the key.
- `npm_config_init_module`: `npm init -y` loaded the module of the key. The spelling `npm_config_init-module` did the same.
- `npm_config_userconfig`: an npmrc with `script-shell=<marker>` and `npm run t` ran the marker.
- Probes that ran no marker, which the change does not claim: `npm_config_browser` (`npm docs .` asks for the `BROWSER` key instead) and `npm_config_node_gyp` (npm ran its own `node-gyp`).
- Not probed: `GOFLAGS` with `-toolexec`. `go` is not in the devcontainer, so the change does not claim a Go key (see Workflow follow-up in the tasks).
- The callers: no file of `src/` or `tests/` gives one of the nine refused keys as a caller override. `src/devops_cli/roadmap/implement_step.py` puts `UV_PYTHON` in the environment of a shell of the agent. That path does not use `build_subprocess_env`. No `uv` call of `src/` uses `--active`, and no child reads `VIRTUAL_ENV`: `install_tools` names its interpreter with `-p`.

## Existing Tool Considered

The default `env_delete` table of sudo is the maintained, open list of environment keys that change the code that a program runs. It lists no key of uv or npm. No library publishes a list for import, so the constant names the source of each key, as #2205, #2429, #2483, #2633 and #2672 decided. The match keeps `fnmatch.fnmatchcase` of the standard library. The change builds no new code path: it adds names to the existing tuple and removes one name from the allowlist. Written cost: about 2500 tokens to build, keep and fix it, and under one hour elapsed.
