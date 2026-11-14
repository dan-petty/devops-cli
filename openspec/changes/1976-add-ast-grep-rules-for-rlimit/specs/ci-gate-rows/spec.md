## ADDED Requirements

### Requirement: The constructs row refuses the process-safety calls
The `constructs` row of `devops ci` SHALL report a violation for a `resource.setrlimit` call whose limit argument is `resource.RLIMIT_NPROC`, for `os.set_blocking` or `fcntl.fcntl` on a literal descriptor 0, 1 or 2 that sets it non-blocking, and for an `os.killpg` call outside the guard-holding functions of `src/devops_cli/core/process.py`. It SHALL report no violation for a literal descriptor above 2.

#### Scenario: A limit of RLIMIT_NPROC
- **WHEN** The rule runs on a module that calls `resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))`
- **THEN** ast-grep reports one violation at the call

#### Scenario: A standard descriptor set non-blocking
- **WHEN** The rules run on a module that calls `os.set_blocking(0, False)` and `fcntl.fcntl(1, fcntl.F_SETFL, fcntl.O_NONBLOCK)`
- **THEN** ast-grep reports one violation at each call

#### Scenario: A descriptor above 2
- **WHEN** The rules run on a module that calls `os.set_blocking(3, False)` and `fcntl.fcntl(3, fcntl.F_SETFL, fcntl.O_NONBLOCK)`
- **THEN** ast-grep reports no violation

#### Scenario: A bare process-group signal
- **WHEN** The rule runs on a module that calls `os.killpg(os.getpgid(pid), signal.SIGTERM)` at module level
- **THEN** ast-grep reports one violation at the call

#### Scenario: A guarded process-group signal
- **WHEN** The rule runs on a module whose guard-holding function calls `os.killpg(pgid, sig)`
- **THEN** ast-grep reports no violation

### Requirement: Each process-safety rule joins the construct gate
Each of the three process-safety rules SHALL set `severity: error`, SHALL name `src/**` in its `files`, and SHALL have one entry in `CONST_AST_GREP_RULE_FILES` and one in `VIOLATIONS` of the construct gate. Its case file SHALL hold a valid case and an invalid case.

#### Scenario: The rule set and the violation table
- **WHEN** The construct gate reads the committed rule files and its violation table
- **THEN** It reports no missing rule, no rule outside the table, and no rule without a valid and an invalid case
