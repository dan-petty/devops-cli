# Tasks

## 1. Tab Validation and Dead Code Removal

- [x] 1.1 Add failing test in `tests/test_ui_dashboard.py` asserting unknown `--tab` values are rejected with `ValidationError` and valid tabs listed from `CONST_DASHBOARD_DOMAINS` (`uv run pytest tests/test_ui_dashboard.py`)
- [x] 1.2 Implement error catalog message in `src/devops_cli/lang/en/errors.py` and `--tab` validation in `src/devops_cli/commands/dashboard.py` (`uv run pytest tests/test_ui_dashboard.py`)
- [x] 1.3 Remove `refresh_all` from `src/devops_cli/ui/refresh.py` and remove its test from `tests/test_ui_reactive.py` (`uv run pytest tests/test_ui_reactive.py`)
- [x] 1.4 Regenerate documentation and verify static checks (`uv run devops docs generate --sync-readme && uv run devops ci test tests/test_ui_dashboard.py tests/test_ui_reactive.py`)

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
