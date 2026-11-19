# Proposal: #5585

## Why

Issue #5585: `src/devops_cli/roadmap/runner_tools.py` holds copies of tool versions: `UV_VERSION`, `GH_VERSION`, `NODE_MAJOR`, `ACTIONLINT_VERSION` and a Python pin made from `DEFAULT_PYTHON_VERSION`. Each copy repeats a pin of `Dockerfile`. Tests compare the copies with the Dockerfiles, and two Renovate custom managers write the uv and Node copies. So a tool bump changes a `.py` file under `src/`. The `Semantic PR title` check then asks for a `fix` title, and a `fix` title starts the `Fail-to-Pass Check`. That check fails, because no test of a pin value is allowed (pull request #6370). The owner rule of 2026-11-19 ("we are not a package manager") says that no tool version stays copied in a `.py` file, and that no test compares pins across files.

## What Changes

- `runner_tools.py` holds no tool version. The constants `UV_VERSION`, `GH_VERSION`, `NODE_MAJOR` and `ACTIONLINT_VERSION`, the field `RunnerTool.pin`, the Python pin, and the imports of `DEFAULT_PYTHON_VERSION` and `load_tools_lock` go.
- The check of the image is a presence check: each program is on PATH, and its version command exits 0. A dev dependency and the project keep their compare with the installed distribution (`importlib.metadata`), because the image itself holds that version. The check of a tool of the lock no longer runs `devops install-tools --check`. The constants `TOOLS_DIR`, `TOOLS_BIN_DIR` and `USER_DATA_ROOT_VARIABLE`, which only that call used, go.
- The messages: `runner_tool_off_pin` goes, `runner_tool_version` becomes `runner_tool_other_version` and names the installed version, and `runner_tools_ready` says `All <n> runner tools run.`
- The tests that compare pins or read `tools.lock` go: the pins of the table against the Dockerfiles, the scanned tools against their image pins, the tools of the lock against the table, the `--tool` steps of the `runner-tools` stage, and the two tests of the link check of a tool of the lock. The tests of one tool use a dev dependency.
- `.github/renovate.json` loses the two custom managers that write `runner_tools.py`. The descriptions of the `uv`, `gh` and `node` groups and of the `src/devops_cli/**` rule no longer name the runner tools table.
- A comment of `Dockerfile`, `docs/CLUSTER.md` and `docs/SDLC.md` describe the presence check and the managers.
- The change alters a message of `devops_cli.lang` and what the build of the runner image checks, which a consumer observes. So it has spec deltas for `roadmap-implement-runner` and `release-concurrency-and-renovate`.
- These stay, as the issue says: the smoke step of the image, which runs `python -m devops_cli.roadmap.runner_tools`; the MCP `--check` lines of `ci.yml` and `release.yml`; and the `DEFAULT_PYTHON_VERSION` pattern of the Python custom manager. gh in `Dockerfile` stays a manual bump, with one copy only.

## Capabilities

- Modified: `roadmap-implement-runner` (The runner stage holds the tools of a step; The runner image holds each tool that the gate and the hooks need; The build of the runner image fails on a missing tool, renamed from "The build of the runner image fails on a missing tool or a wrong pin").
- Modified: `release-concurrency-and-renovate` (Every pin of the repository has a Renovate manager; An update of runtime code has the prefix of a release).

## Impact

- A Renovate update of uv or Node, and a bump of gh or actionlint, changes no file under `src/`. Such a pull request needs no `fix` title for the `Semantic PR title` check, and the `Fail-to-Pass Check` does not start.
- The build of the runner image no longer fails when a tool prints another version than a copy in the module. `Dockerfile` and `tools.lock` stay the only pins, and the build installs what they name.
- Pull request #6166 changes other lines of `runner_tools.py`, of its test file and of `Dockerfile`, and line 68 of `docs/CLUSTER.md`. It must rebase on this change.
- The change fits one pull request.

## Feasibility

Read on `origin/main` at 252b6bcef on 2026-11-19:

- `git grep -nE '^(UV|GH|ACTIONLINT)_VERSION|NODE_MAJOR' -- src` finds only `src/devops_cli/roadmap/runner_tools.py:43-46`. The other users of the constants are `tests/roadmap/test_roadmap_runner_tools.py` and two custom managers of `.github/renovate.json`.
- `_pin_failure` is the only user of `TOOLS_DIR`, `TOOLS_BIN_DIR`, `USER_DATA_ROOT_VARIABLE` and the message `runner_tool_off_pin`.
- `src/devops_cli/github/release_title.py` counts each path under `src/devops_cli/` as runtime code, and the path filter of `.github/workflows/fail-to-pass.yml` is `src/**/*.py`. So a pin in a `.py` file needs a `fix` title and starts the check. The comments of #5585 show this on #6370.
- `is_source_code` in `src/devops_cli/ci/fail_to_pass.py:357-366` reads only the path. The requirement "A pin-only Python module is no source code" of the refine design is not built: no module under `src/` holds only a tool version after this change, and `runner_tools.py` holds functions. `design.md` gives the evidence.
- The dockerfile manager of Renovate reads `FROM ghcr.io/astral-sh/uv` and `FROM node` in `Dockerfile`, so the `uv` and `node` groups keep members without the custom managers, and the rule for a base image of `Dockerfile` gives them `fix(deps):`.

## Existing Tool Considered

The pins of `Dockerfile` and `tools.lock`, which the Renovate dockerfile, regex and pip-compile managers read, cover the need: they hold each version once. The change builds nothing. It deletes internal code: the four version constants, `RunnerTool.pin`, `_pin_failure`, the `IMAGE_PIN` and `TOOLS_LOCK` branches of `expected_text`, three path constants, one message, two custom managers, and the tests that compare pins or read `tools.lock`.
