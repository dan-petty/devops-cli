# Tasks

## 1. The Claude settings

- [x] 1.1 Add the test of the two values in the scaffolded Claude settings, and see it fail
  - Verification: `$ uv run devops ci test tests/commands/test_devcontainer.py`
- [x] 1.2 Set `VIRTUAL_ENV` to `""` and `UV_COMPILE_BYTECODE` to `"0"` in `.claude/settings.json` and in `claude_settings.json.j2`
  - Verification: `$ uv run devops ci test tests/commands/test_devcontainer.py tests/core/test_third_party_telemetry.py`
  - Verification: `$ claude -p` in the worktree runs `uv run python -c 'import sys;print(sys.prefix)'` and gets only the worktree `.venv` path

## 2. Documents

- [x] 2.1 Describe the two values in `CONTRIBUTING.md` (Shell notes for agents, item 3)
  - Verification: `$ uv run devops ci docs`
