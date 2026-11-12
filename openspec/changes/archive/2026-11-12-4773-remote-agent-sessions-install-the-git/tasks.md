# Tasks

## 1. Claude Code cloud sessions install the git hooks (behavior)

- [x] 1.1 Write a failing test: the settings that `devops devcontainer init` scaffolds hold one SessionStart command hook with the matcher `startup|resume` that installs the hooks only when `CLAUDE_CODE_REMOTE` is `true`
  - Verification: `$ uv run devops ci test tests/commands/test_devcontainer.py`
- [x] 1.2 Add the hook to `src/devops_cli/templates/claude_settings.json.j2` and `.claude/settings.json`
  - Verification: `$ uv run devops ci test tests/commands/test_devcontainer.py`

## 2. The Copilot cloud agent installs the git hooks

- [x] 2.1 Add the step `uv run pre-commit install --install-hooks` to `.github/workflows/copilot-setup-steps.yml`, and add the command to the list of the workflow contract test
  - Verification: `$ uv run devops ci --check --only actionlint,zizmor`
  - Verification: `$ uv run devops ci test tests/invariants/test_workflow_contracts.py`

## 3. Documents

- [x] 3.1 Say in `CONTRIBUTING.md` how each agent host installs the hooks
  - Verification: `$ uv run devops ci docs`

- Manual check, repeatable: clone the branch into a temporary directory, read the command from `.claude/settings.json`, and run it with `bash -c` and `CLAUDE_PROJECT_DIR` set to the clone. With `CLAUDE_CODE_REMOTE=true`, `.git/hooks/pre-commit` and `.git/hooks/pre-push` exist and the exit code is 0. With the variable not set, the clone has no hook and the exit code is 0.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
