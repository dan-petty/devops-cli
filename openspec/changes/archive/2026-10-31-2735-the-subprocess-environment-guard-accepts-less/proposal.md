# Proposal

## Why

#2735 reports that build_subprocess_env in src/devops_cli/core/process.py refuses LESSOPEN and LESSCLOSE but accepts LESS. The less(1) pager reads options from LESS, and the +! option runs a shell command. Git and gh use less as their default pager, so a caller override of LESS is a code-execution path. A probe with less 668 confirmed that LESS=+! made git --paginate and gh help reference run a marker program.

## What Changes

- Add "LESS" to CONST_CODE_LOADING_ENV_PATTERNS in src/devops_cli/config/constants.py so that _is_env_override_refused raises SecurityError for any caller override of LESS.
- Add a test case asserting that build_subprocess_env raises SecurityError for a LESS override, with and without isolation, and that LESSOPEN refusal is unchanged.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `subprocess-environment`: Refuse LESS override

## Impact

- Code: `src/devops_cli/config/constants.py`
- Tests: `tests/test_process.py`

## Feasibility

- The premise is confirmed against the inputs. src/devops_cli/core/process.py imports CONST_CODE_LOADING_ENV_PATTERNS from devops_cli.config.constants and passes it to _is_env_var_denied inside _is_env_override_refused. The issue body states the constant already holds LESSOPEN and LESSCLOSE from #2205 and #2483, and that LESS is absent, so it passes through. The reproduction command uv run python -c 'from devops_cli.core.process import build_subprocess_env as b; print(b(env={"LESS": "+!x\n"})["LESS"])' returns the key unchanged, confirming the gap.
- First check after the fix: run uv run python -c 'from devops_cli.core.process import build_subprocess_env as b; b(env={"LESS": "+!x\n"})' and confirm it raises SecurityError. Second check: run the new test case in the test file and confirm it passes. Third check: run the existing LESSOPEN and LESSCLOSE test cases and confirm they still pass.

## Existing Tool Considered

No open, maintained tool or library covers this need. The project builds its own environment guard in src/devops_cli/core/process.py. The written cost is one key added to a constant in src/devops_cli/config/constants.py and one test case in the existing test file. No internal code is deleted.
