### Problem Description

`build_subprocess_env` in `src/devops_cli/core/process.py` refuses `LESSOPEN` and `LESSCLOSE` (#2205, #2483) but accepts `LESS`. less(1) reads options from `LESS`, and an option that starts with `+` is a command that less runs at start. The command `!<program>` makes less run a shell command. Git runs less as its default pager, and `gh` runs the pager of `GH_PAGER` or `PAGER`, so a caller override of `LESS` is a code path for git and gh children.

The independent review of #2672 (PR #2732) probed this with real less 668 in a pseudo-terminal, a temporary HOME and a marker program that prints a line. The probe is not mine: I report its result.

- `LESS` with the value `+!<marker>` and a trailing newline made `git --paginate help -a` run the marker.
- The same value made `GH_PAGER=less gh help reference` run the marker.
- `build_subprocess_env(env={"LESS": "+!x\n"})` returns the key unchanged.

### Reproduction Steps

1. Run `uv run python -c 'from devops_cli.core.process import build_subprocess_env as b; print(b(env={"LESS": "+!x\n"})["LESS"])'`.
2. In a temporary directory `<dir>`, write an executable `<dir>/marker` that runs `echo MARKER-RAN >&2`.
3. In a pseudo-terminal, run `env -i PATH=/usr/bin:/bin HOME=<dir> LESS="+!<dir>/marker
" git --paginate help -a`.

### Expected vs Actual Behavior

Expected: `build_subprocess_env` raises `SecurityError` for a caller override of `LESS`, or the design names the reason to accept it. Actual: it returns `LESS` with no error, and a child that starts less runs the program.

### Environment Diagnostics

- DevOps CLI Version: main after #2732 (the PR that refuses the gh and kubectl program keys)
- Execution Environment: DevContainer
- less 668

### Logs, Traces, or Terminal Output

```shell
MARKER-RAN
```

### Pre-Submission Checklist

- [x] I have verified that no sensitive credentials, private keys, or internal tokens are contained in this issue report.
- [x] I have checked existing issues and pull requests to ensure this is not a duplicate.

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=07fb4c222b09ef6bb9e6fc9cd1d5fbb45f6c9a78 -->
## Proposed design

### Problem statement
The subprocess environment guard in build_subprocess_env refuses LESSOPEN and LESSCLOSE but accepts LESS. The less(1) pager reads options from LESS, and an option that starts with + is a command that less runs at start. The ! option makes less run a shell command. Git and gh use less as their default pager, so a caller override of LESS is a code-execution path for their children. A probe with less 668 confirmed that LESS=+! made git --paginate and gh help reference run the marker program.

### Acceptance criteria

### Requirement: Refuse LESS override
build_subprocess_env SHALL raise SecurityError when a caller overrides the key LESS, in upper or lower case.

#### Scenario: Caller sets LESS to a command string
- **WHEN** A caller calls build_subprocess_env with env={"LESS": "+!x\n"}
- **THEN** The call raises SecurityError with the message "Prohibited dangerous environment variable override: 'LESS'"

### Requirement: Refuse LESS with isolation off
build_subprocess_env SHALL raise SecurityError for a LESS override when isolate_env is False.

#### Scenario: Caller sets LESS with isolation disabled
- **WHEN** A caller calls build_subprocess_env with env={"LESS": "+!x\n"} and isolate_env=False
- **THEN** The call raises SecurityError with the same message

### Requirement: Do not refuse LESSOPEN or LESSCLOSE
The refusal of LESS SHALL NOT change the existing refusal of LESSOPEN and LESSCLOSE.

#### Scenario: Caller sets LESSOPEN after the fix
- **WHEN** A caller calls build_subprocess_env with env={"LESSOPEN": "|x %s"}
- **THEN** The call raises SecurityError as before

### Existing Tool Considered
No check has run. No open, maintained tool or library covers this need. The project builds its own environment guard in src/devops_cli/core/process.py. The written cost is one key added to a constant in src/devops_cli/config/constants.py and one test case in the existing test file for build_subprocess_env.

### Key questions
- **Where is the list of refused environment variable keys defined?**: The constant CONST_CODE_LOADING_ENV_PATTERNS in src/devops_cli/config/constants.py holds the patterns. The function _is_env_override_refused in src/devops_cli/core/process.py checks a caller key against this constant via _is_env_var_denied, which uses fnmatch.fnmatchcase for full-string matching. [sources: src/devops_cli/core/process.py, openspec/changes/archive/2026-10-29-2483-refuse-git-code-env-keys/specs/subprocess-environment/spec.md]
- **Should LESS be refused or accepted by the guard?**: Refuse it. The less(1) manual documents that LESS holds options and that +! runs a shell command. The guard already refuses LESSOPEN and LESSCLOSE for the same reason (less runs a filter program). The #2483 spec and ARCHITECTURE.md record the pattern: a key that makes a child run a program is refused. No file in src/ sets or reads LESS for a child, so refusing it breaks no existing caller. (best practice) [sources: openspec/changes/archive/2026-10-29-2483-refuse-git-code-env-keys/specs/subprocess-environment/spec.md, openspec/changes/archive/2026-10-29-2483-refuse-git-code-env-keys/design.md, ARCHITECTURE.md]
  - Chosen: Refuse LESS as a caller override. Consistent with LESSOPEN and LESSCLOSE. less(1) documents +! as a shell command. A probe with less 668 confirmed execution. No project code sets LESS for a child.
  - Rejected: Accept LESS and document the risk. Rejected. The project's own standard (ARCHITECTURE.md, #2483 spec) is to refuse keys that make a child run a program. Accepting LESS would leave a known code-execution path open.
- **Does any code in the project set or read LESS for a child process?**: No. The #2483 design doc states that no file of src/ sets or reads the refused pager keys for a child, and no test sets one. The same applies to LESS: it is not in DEFAULT_ALLOWED_ENV_VARS, not in any prefix, and no caller passes it in extra_allowed_env. [sources: openspec/changes/archive/2026-10-29-2483-refuse-git-code-env-keys/design.md, src/devops_cli/core/process.py]

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
None.
<!-- devops-roadmap-refine:end -->

<!-- devops-roadmap-record {"Effort": "Low", "Priority": "P1-High", "Status": "In Review", "Value": "High", "implement.branch": "fix/2735-the-subprocess-environment-guard-accepts-less", "implement.group": "1", "implement.job": "devops-cli-runner-20261031-181251-c648", "implement.job_state": null, "implement.pr": "2896", "implement.sha": "2edee538d180162b1e00db934ec64f5287b6bcd1", "implement.spend": "{\"requests\": 46, \"input_tokens\": 1500262, \"output_tokens\": 5112}", "implement.stopped": null, "refine.alternatives_asked": null, "refine.block_paths": null, "refine.blocked_by": null, "refine.body_hash": "4e72cf3db8417a602c45e2fefec585ea45a5b7e4536d6b44b9743094b404adbc", "refine.failed_body_hash": null, "refine.needs_split": "false", "refine.next_step": "ready", "refine.section_hash": "07b318b0c07eb90c06b88bde28548b25a75681a854009f2874df734280467ad1", "stage.branch": null, "stage.file_cap": null, "stage.groups": null, "stage.needs_split": null, "stage.pr": null, "stage.ready": null, "stage.sha": null} -->
