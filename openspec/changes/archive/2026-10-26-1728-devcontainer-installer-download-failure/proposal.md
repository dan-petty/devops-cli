# Proposal

## Why

In #1728, `devops devcontainer post-create` reports that a developer tool was installed when its download failed.
The user sees a success message, but the tool binary is missing from the container.
The helper `_bootstrap_developer_tools` in `src/devops_cli/commands/devcontainer.py` runs curl pipelines through `sh -c`.
A shell pipeline without `pipefail` exits with the return code of the last command in the pipeline.
When curl fails, the shell pipeline receives empty standard input and exits with status 0.
`_bootstrap_developer_tools` then reports a successful installation instead of the existing failure warning.

## What Changes

- Update installer command definitions in `_bootstrap_developer_tools` to run through `bash -o pipefail -c`.
- Ensure failed downloads for `uv` and `claude` CLI tools cause the command to return a non-zero exit status.
- Add specification unit tests in `tests/test_devcontainer.py` verifying that failed installer downloads report warnings and successful downloads report installations.
- This change changes error detection in post-create setup without changing any specification in `openspec/specs/`.

This change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/commands/devcontainer.py`: updates shell execution parameters for developer tool bootstrap commands.
- `tests/test_devcontainer.py`: adds specification tests for failed and successful downloads of uv and claude.

## Feasibility

- Confirmed with `sh -c "false | sh"` returning 0 and `bash -o pipefail -c "false | sh"` returning 1.
- Confirmed with a failing curl (exit status 7) running under `devops devcontainer post-create` returning success in unpatched code.
- Confirmed with `bash -o pipefail -c "curl ..."` propagating curl non-zero exit codes to the caller.

## Existing Tool Considered

Bash provides the `-o pipefail` shell option.
Using `-o pipefail` avoids complex custom download logic or temporary files.
No internal library code is deleted.
