# Design

## Context

`devops devcontainer post-create` installs essential developer tools if they are missing from the container image.
The tools include `uv`, `pre-commit`, and `claude`.
The installers for `uv` and `claude` download and execute remote shell scripts using curl piped to a shell.
Previously, these pipelines ran under `sh -c "curl ... | sh"` and `sh -c "curl ... | bash"`.
Without `pipefail`, a shell pipeline exits with the return code of the rightmost command.
If curl fails during download, the downstream shell receives end-of-file and exits with status 0.
Therefore, `run_subprocess` receives exit code 0 and reports success.

## Goals / Non-Goals

**Goals:**

- Ensure a failed curl download in `_bootstrap_developer_tools` causes the command to exit with non-zero status.
- Report the warning message when downloading `uv` or `claude` fails.
- Report the success message when downloading succeeds.
- Verify behavior with test-first specification tests that fail on unpatched code and pass on patched code.

**Non-Goals:**

- Change the upstream installer script URLs.
- Change the installation method for `pre-commit`, which installs via `uv tool install pre-commit`.
- Change `_bootstrap_managed_tools` or keyring package installation logic.

## Decisions

### Decision 1: Use `bash -o pipefail -c` for Pipeline Execution

Update the command invocation in `_bootstrap_developer_tools` to:
`["bash", "-o", "pipefail", "-c", "curl -LsSf https://astral.sh/uv/install.sh | sh"]`
and
`["bash", "-o", "pipefail", "-c", "curl -fsSL https://claude.ai/install.sh | bash"]`.

*Alternatives considered:*
- Downloading the installer script to a temporary file via Python HTTP client: rejected because it requires temporary file management, permission handling, and diverges from upstream vendor installation patterns.
- Checking for binary existence after running the installer: rejected because it hides the underlying exit code and masks installation errors as missing binaries.

## Rejected Alternatives

- Downloading via Python HTTP client: rejected because Bash `pipefail` solves the problem directly with existing standard shell capabilities.
