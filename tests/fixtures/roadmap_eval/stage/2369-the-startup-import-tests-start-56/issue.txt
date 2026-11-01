## Problem or Motivation

`tests/test_cli_startup_imports.py` is the largest file of the suite in test time. In a full run of 2026-10-27 on a 16-CPU host (11,285 tests, 287 s of pytest), its 56 tests took 204 s of the 2,423 s that all tests took together (8.4%). It runs no line of `src/` that another test does not run, and it is a structural budget on what `devops <command>` imports, so it stays. Its cost is the problem.

Each test starts a fresh interpreter under `-X importtime` and runs `devops <argv>` (`_probe_startup_imports`, line 443), then parses the `importtime` text of stderr. There are 56 probes: `--version`, `--help`, one `<command> --help` for every command group, the argvs of the budget tables, and three controls. Three tests of the file are among the 13 slowest tests of the run: `test_ai_agents_and_providers_import_no_model_sdks` (16.8 s in its call), `test_pydantic_ai_exceptions_lazy` (11.6 s) and `test_startup_structural_budget_fails_when_extra_heavy_package_imported` (9.4 s).

The 204 s is the cost of the probes, not a cost that the 16 workers repeat. The same file in one process (`pytest tests/test_cli_startup_imports.py -n 0`) took 233 s of CPU time (203 s user, 30 s system) for 56 probes, about 4.2 s of CPU for each. That run was on a host with a load average of 26 to 29, so the figure is high. A bare `import devops_cli.main` took about 1 s of CPU on the same host. The rest of each probe is the cost of `-X importtime` (a line for each import, written to stderr and parsed in Python), of the work of the command's help, and of the contention.

This issue is a sub-issue of #2356.

## Proposed Solution & Architectural Design

Measure first, then change one thing at a time. Each step has its own number in the pull request.

1. **Split the cost.** For one `ci --help` probe, time (a) the interpreter alone, (b) `import devops_cli.entry`, (c) the help of the group, (d) the same with and without `-X importtime`, and (e) the parse of stderr. Report CPU time (user plus system), not wall time: a loaded host moved the wall time of the whole suite from 3 m 28 s to 5 m 3 s and 6 m 27 s on 2026-10-27 (#2356).
2. **Read the modules a different way.** The budget asks which modules a command loads. `-X importtime` is only needed for the report of the ten slowest imports in a failure message. A probe without it, with `sys.modules` printed at the end, may cost far less. If it does, run the probe again with `-X importtime` only when a budget fails, to build the message.
3. **Keep one interpreter for each argv.** A module that one argv imports stays in `sys.modules`, so two argvs cannot share an interpreter. The fixed cost of an interpreter is the floor, and step 1 says how high it is.
4. **Keep the budget exactly as strict.** No limit moves. The control that proves the probe fails when a heavy package is imported stays.

**Acceptance:** the file takes at most half of its present CPU time, measured over three runs of `pytest tests/test_cli_startup_imports.py -n 0` on the same host, with the same 56 probes and the same limits.

## Target Subsystem

SDLC, Git & PR Governance

## Existing Tool Considered

- **`python -X importtime`** is the tool in use. It stays for the failure message.
- **`pytest-xdist`** is in use and runs the probes on all workers.
- **`pytest-benchmark`** and **`pyinstrument`** time code inside a process. The cost here is in the start of processes, so the timings of step 1 use `time` and `-X importtime`, and nothing new is built.


Source: https://github.com/dan-petty/devops-cli/issues/2356

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=2ae3772423fe264ad4fd2d9ee6681535015bface -->
## Proposed design

### Problem statement
The startup-import test file takes 204 s of the suite's 2,423 s. Each of its 56 probes starts a fresh CPython interpreter. The proposed fix of dropping `-X importtime` is shown false by paired measurement: the flag adds no measurable cost. The real per-probe cost is the import of the main module and the work of the command help. Issue #2164 plans to move this budget into a `devops ci` row, which conflicts with changes to the pytest file.

### Acceptance criteria

### Requirement: Reduced per-probe CPU time
The file SHALL take at most half its present CPU time over three runs of `pytest tests/test_cli_startup_imports.py -n 0` on the same host.

#### Scenario: Three consecutive runs on the same host
- **WHEN** The test file is run three times with `-n 0` on the same host after the change
- **THEN** The total CPU time (user plus system) across the three runs is at most half the baseline measured the same way before the change

### Requirement: All probes pass
All 56 probes SHALL execute and pass with no failures or errors.

#### Scenario: Full test file run
- **WHEN** The test file is run with `pytest tests/test_cli_startup_imports.py -n 0`
- **THEN** The run reports 56 passed tests with no failures or errors

### Requirement: Budget limits unchanged
All four budget limit constants SHALL retain their integer values.

#### Scenario: Constant values after the change
- **WHEN** The constants `DEFAULT_STARTUP_IMPORT_MODULE_LIMIT_MAIN_AND_VERSION`, `DEFAULT_STARTUP_IMPORT_DEVOPS_MODULE_LIMIT_MAIN_AND_VERSION`, `DEFAULT_STARTUP_IMPORT_MODULE_LIMIT_COMMAND_HELP`, and `DEFAULT_STARTUP_IMPORT_DEVOPS_MODULE_LIMIT_COMMAND_HELP` are read after the change
- **THEN** Each constant has the same integer value as before the change

### Requirement: Control test passes
The control test SHALL prove the budget fails when a heavy package is imported.

#### Scenario: Control test execution
- **WHEN** `test_startup_structural_budget_fails_when_extra_heavy_package_imported` is run
- **THEN** The test passes, confirming the budget correctly detects the extra heavy import

### Requirement: Failure message intact
A failing budget SHALL report the ten slowest imports in its assertion message.

#### Scenario: Budget breach message
- **WHEN** A budget limit is breached during a probe
- **THEN** The assertion message includes the ten slowest imports by cumulative seconds

### Existing Tool Considered
No alternatives check has run. No open, maintained tool or library covers the need of reducing the fixed cost of CPython interpreter startup and module import. The cost is inherent to the runtime. The body lists `python -X importtime`, `pytest-xdist`, `pytest-benchmark`, and `pyinstrument`, but paired measurement shows none is the cost driver. The real cost is the import of the main module and the work of the command help, which no external tool can reduce.

### Key questions
- **Does dropping `-X importtime` reduce the per-probe CPU time?**: No. Paired, alternating measurements show the ratio of CPU time with and without the flag is 0.97 to 1.02, which is noise. The flag is not the cost driver. [sources: tests/commands/test_cli_startup_imports.py:448]
- **What is the real per-probe cost breakdown?**: A bare interpreter costs 0.03 s. `import devops_cli.entry` costs 0.25 to 0.36 s. The rest is the work of `main` and the command help, which the budget must run. For `ai agents --help`, the total is 3.3 to 3.4 s. [sources: tests/commands/test_cli_startup_imports.py:448]
- **Does issue #2164 conflict with changes to this test file?**: Yes. Issue #2164 plans to move the startup-import budget into a `devops ci` row. Work on the pytest file would conflict with it. A new item can re-scope this issue after #2164 is delivered. (best practice) [sources: tests/commands/test_cli_startup_imports.py]
  - Rejected: Work on the pytest file now. Conflicts with #2164, which plans to move the budget into a `devops ci` row.
  - Chosen: Wait for #2164, then re-scope. Avoids conflict. The re-scoped item targets the real cost: the import of the main module and the work of the help.
- **Can two different argvs share one interpreter process?**: No. A module imported by one argv stays in `sys.modules` and contaminates the count for the next argv. Each argv needs its own fresh interpreter. [sources: tests/commands/test_cli_startup_imports.py:395]
- **Do the budget limits change?**: No. All limits stay exactly as they are. The control test that proves the budget fails when a heavy package is imported stays. (best practice) [sources: tests/commands/test_cli_startup_imports.py:30, tests/commands/test_cli_startup_imports.py:492]
  - Rejected: Change the limits. The body states no limit moves. The budget must stay exactly as strict.
  - Chosen: Keep the limits unchanged. The body and the reply both confirm the limits stay.

### Open questions
- Is the plan folder for this issue still present? (missing verified source)

### Fit
Needs splitting into 1 items:
1. Re-scope the startup-import budget after #2164 moves it into a `devops ci` row, targeting the real per-probe cost of the main module import and the help work

### Suspected block
Issue #2164 (move startup-import budget into a `devops ci` row) must be delivered first. Work on the pytest file would conflict with it.

### Dependencies
#2164
<!-- devops-roadmap-refine:end -->

<!-- devops-roadmap-record {"Effort": "Medium", "Owner": "Agent", "Priority": "P2-Medium", "Status": "New", "Value": "Medium", "refine.alternatives_asked": null, "refine.block_paths": "tests/commands/test_cli_startup_imports.py", "refine.blocked_by": null, "refine.body_hash": "e8beb2f7126cda948cda0a644404553bbea28107cfaf4618e45d7158c35eb2ee", "refine.failed_body_hash": null, "refine.needs_split": "true", "refine.next_step": "person", "refine.section_hash": "d673a505f628b31a6e5cb6bd450e41e3d1eda44c6c576577eff3f40277cbbd52", "stage.branch": "perf/2369-the-startup-import-tests-start-56", "stage.file_cap": null, "stage.groups": "[[\"Replace -X importtime with sys.modules dump in the probe\", 3098], [\"Add timed re-probe for the failure diagnostic message\", 3102]]", "stage.needs_split": null, "stage.pr": "2985", "stage.ready": "2985", "stage.sha": "457039fc37591c9f93e3327bc4cdaa7d703c7a39"} -->
