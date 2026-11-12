# Tasks

## 1. Allow the standard project commands (behavior)

- [x] 1.1 Write a failing test: `devops devcontainer init` writes `.claude/settings.json` with the full allow list and the unchanged deny list.
  - Verification: `$ uv run devops ci test tests/commands/test_devcontainer.py`
- [x] 1.2 Add the rules to `src/devops_cli/templates/claude_settings.json.j2` and to `.claude/settings.json`.
  - Verification: `$ uv run devops ci test tests/commands/test_devcontainer.py`

## 2. Documents

- [x] 2.1 Give the allow list in CONTRIBUTING.md, with the commands it does not allow and the planned `infra` group that `Bash(uv run devops *)` covers.
  - Verification: `$ uv run devops ci docs`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
