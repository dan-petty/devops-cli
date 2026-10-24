# Proposal

## Why

Issue #1978, part 1 of the tracker #772: mypy and the review canary started their tools outside the `ToolExecutor` seam. `run_mypy_scan` in `src/devops_cli/security/mypy.py` took no executor. It called `run_subprocess` with `python -I -m mypy`, where `python` is the interpreter of the `.venv` of the reviewed checkout, else the interpreter that runs devops-cli. `run_tool_canary` in `src/devops_cli/review/canary.py` also started each tool through `run_subprocess`. So a review ran mypy and every canary as plain child processes, also when the review gave its scanners another executor, and the review kept no record of the mypy run. Two review test files patched `run_mypy_scan`, because mypy had no fake, and the root conftest patched the `run_subprocess` of the canary module.

A `ToolRequest` named a tool of the tools lock, and the executor found its binary on the PATH of the host. So a request could not name the interpreter of the reviewed `.venv`.

## What Changes

- `ToolRequest` has one optional field more, `program`: the absolute path of the program that starts the tool when the PATH of the host does not name it. `DirectToolExecutor` and `SandboxToolExecutor` start that program by its path, and never by the file that its link leads to. The `ToolExecutor` protocol, `ToolResult` and `ToolRun` do not change. A request refuses a relative `program`, and the sandbox refuses a `program` that is no file before anything starts.
- The record of a run of a `program` names the tool in `tool`, as before, and the program by its file name as the first element of `argv_template`. Its `version` and `binary_sha256` name the distribution of the tool in the environment of the program (`resolve_tool_version_and_sha(tool, program)`). With no such distribution, `binary_sha256` is the SHA-256 of the program file, and `version` is the pin of `tools.lock`, else `unknown`.
- `run_mypy_scan` takes a `tool_executor` and builds a `ToolRequest`. The interpreter is its `program`, and the environment of the interpreter is a read-only bind. The request names the config file in `config_files` and the targets as `{targets}`. Mypy gets its cache directory through `MYPY_CACHE_DIR`, so the template holds no path. A run that times out gives a failed outcome that names the time, and a request that the executor refuses gives a failed outcome with the reason, as for the other scans.
- The review gives mypy the executor that it gives every other scanner. So the mypy run is in the Tool Runs table of `review.md` and in `profile.json`.
- `run_tool_canary` takes a `tool_executor` in place of its `runner` callable, and `build_canary_request` replaces `build_canary_command`. The review gives the canaries the executor that it wraps. A canary checks a tool on a fixture of its own and scans nothing of the review, so the review keeps no record of a canary run. The canaries of Ruff and Bandit start the tool as their scans start it: the direct executor starts it by its name on PATH, not by a path beside the running interpreter.
- Tests: no review test patches `run_mypy_scan`. The mypy scans of `tests/test_review_tool_runs.py` and `tests/test_scanner_tool_executor.py` run over `ToolExecutorFake`. The root conftest answers each canary run of `DirectToolExecutor` with the recorded canary output through `ToolExecutorFake`, in place of the patch of the `run_subprocess` of the canary module.
- `docs/SELF_IMPROVEMENT.md` says what the record of a mypy run holds, and `docs/TESTING.md` says how a test fakes mypy and the canaries.
- The record of the mypy run is in `profile.json` and in `review.md`, where a consumer sees it. So the change carries a spec delta. It extends the capability `review-tool-runs`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `review-tool-runs`: ADDED requirements for a request that names a program, for the mypy run of a review, and for the canaries of a review.

## Impact

- Code: `src/devops_cli/security/tool_executor.py` (`ToolRequest`, the argument template, `DirectToolExecutor`, `SandboxToolExecutor`), `src/devops_cli/review/canary.py` (`resolve_tool_version_and_sha`, the canary runner), `src/devops_cli/security/mypy.py` (`run_mypy_scan`), `src/devops_cli/ai/review/pipeline.py` (the orchestrator gives its executor to mypy and to the canaries) and `src/devops_cli/config/constants.py` (`CONST_CANARY_WORKDIR_PREFIX`, `CONST_MYPY_CACHE_DIR_ENV`).
- Tests: `tests/conftest.py`, `tests/test_tool_executor_contract.py`, `tests/review/test_review_tool_binary_digest.py`, `tests/test_scanner_tool_executor.py`, `tests/test_review_tool_runs.py`, `tests/test_review_canary.py` and `tests/test_review_ruff_mypy_evidence.py`.
- Documentation: `docs/SELF_IMPROVEMENT.md` and `docs/TESTING.md`.
- The sandbox stays off by default (#2096). design.md says what the sandbox needs before mypy can run in it.

## Feasibility

- Code, at base 51a8e0a5: `run_mypy_scan` started `[<checkout>/.venv/bin/python or sys.executable, "-I", "-m", "mypy", ..., "--cache-dir", <path>, <files>]` through `run_subprocess`. `_run_live_canary_command` started each canary command through `run_subprocess`. `DirectToolExecutor.run` started `[request.tool, ...]`, and `SandboxToolExecutor.command` started `resolve_tool_binary(request.tool)`, which reads `shutil.which`. `ToolRequest` refuses a field it does not know (`extra="forbid"`). So no request could name a program that the PATH does not name.
- Tests, at base: `tests/test_review_tool_runs.py:107` and `tests/test_scanner_tool_executor.py:305` patched `devops_cli.security.mypy.run_mypy_scan`, and `tests/conftest.py` patched `devops_cli.review.canary.run_subprocess`. Command output: with the patch removed on the base, the floor of the suite fails `test_a_review_profile_holds_one_row_per_tool_run_with_every_field` with `process edge reached without a fake: python -I -m mypy --python-version=3.14 --config-file ...`.
- Command output on the devcontainer: the `.venv/bin/python` that uv makes is a link to the interpreter that uv installed below the home directory. The path of the link finds the `.venv`, and the resolved path does not.
- Library, mypy 2.3.1: `mypy/main.py` reads `MYPY_CACHE_DIR` after the config file, and its help text says "Define MYPY_CACHE_DIR to override configuration cache_dir path". A `--cache-dir` on the command line wins over the variable, and the review passes none.
- Library, CPython 3.14.7: `importlib.metadata.distributions(name=..., path=...)` finds a distribution by its normalized name in the given directories. `sysconfig.get_path(<key>, "venv", vars=...)` gives the site-packages directories of an environment, as #1984 uses it.
- Command output: bubblewrap and prlimit are on the devcontainer. The shared contract case for a request that names a program runs over the real sandbox executor, with the program in a read-only bind, and passes.

## Existing Tool Considered

- The `ToolExecutor` seam of #772 Part A (#1914), `ToolExecutorFake` and its contract suite cover the need. The change adds one optional field to `ToolRequest`, and no executor, fake or process runner. `run_subprocess` of `core.process` stays the only code that starts a process.
- Mypy's own `MYPY_CACHE_DIR` carries the cache directory.
- `importlib.metadata` and `sysconfig` name the distribution of the tool, as for #1984.
- Internal code that the change deletes: `_run_live_canary_command`, `build_canary_command`, `_CANARY_COMMAND_BUILDERS` and the six `_build_*_canary_cmd` builders (argument builders replace them), the `runner` parameter of `run_tool_canary`, the `run_subprocess` calls of `mypy.py` and `canary.py`, the two `mypy_set_aside` fixtures and `_recorded_canary_subprocess` of the root conftest.
