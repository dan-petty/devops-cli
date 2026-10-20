# Task: The Startup-Import Checks Start One Interpreter per Command Line (#1733)

**Issue**: [#1733](https://github.com/dan-petty/devops-cli/issues/1733)
**Scope**: scope/ci
**Feasibility**: Counting the `python` starts in `tests/test_cli_startup_imports.py` showed 63, of which 9 measured a command line another test had already measured:
- the root `--help` in four tests;
- `--version`, `ci --help`, `workspace --help`, `ai --help`, `review --help` and `k8s --help` twice each.

Interleaved A/B runs showed that one start costs the same CPU through the shared probe as through the old ones. The saving therefore comes from fewer starts, not cheaper ones. A start per command line is the thing being measured, since each command's imports must not count against another's.

## Description

- [x] The telemetry, heavy-module and two budget tests are one table-driven test, `test_cli_help_startup_imports`.
  - It has one item per distinct help command line (42), each run once under `-X importtime`. That run is checked against every rule that applies:
    - the heavy modules in `CONST_CLI_HEAVY_MODULES`, both in `sys.modules` and in the importtime report;
    - logfire, opentelemetry.sdk and pydantic_ai for the root, `ci` and `workspace` help (#858);
    - #1687's two budgets.
  - The probe calls `devops_cli.entry.main` as the `devops` script does. Each devops-cli count is therefore one higher, because `devops_cli.entry` replaces `runpy`.
- [x] `test_cli_dry_run_imports_only_plan_dependencies` has one item per command line, so its runs can land on different workers. Its docstring records why the review case can still take over 5s: it imports about 2,500 modules of the review pipeline.
- [x] The file starts 54 interpreters instead of 63, and holds 55 tests instead of 62. Every assertion is kept.
  - Back-to-back runs at load 20-70 went from 321s to 157s and from 314s to 166s at `-n 0`. Load inflates those numbers.
  - The structural saving is the 9 starts, about 15 CPU-seconds at load 16.
- [x] Red evidence:
  - kubernetes injected into `commands/ci.py`, logfire into `commands/workspace.py`, and a command-help limit lowered to 100: 9 command lines failed, the rest passed.
  - docker injected into `commands/k8s/__init__.py`: the `k8s deploy-stack --dry-run` case failed.
- The remaining cost is one interpreter per command line, which the checks measure. Sharing the import of `devops_cli.main` through a fork server would add machinery for about 0.8 CPU-seconds per start, so it is not done.
