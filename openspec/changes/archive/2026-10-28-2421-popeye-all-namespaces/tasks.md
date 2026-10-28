# Tasks

## 1. Core Implementation

- [x] 1.1 Write failing tests asserting `-A` is present when namespace is None in `tests/test_command_builders.py` and `tests/test_secops.py`, and verify failure with `uv run pytest tests/test_command_builders.py tests/test_secops.py -k popeye`
- [x] 1.2 Update `build_popeye_cmd` in `src/devops_cli/config/commands.py` to include `-A` when namespace is omitted, and verify tests pass with `uv run pytest tests/test_command_builders.py tests/test_secops.py -k popeye`
- [x] 1.3 Run full CI static checks and tests with `uv run devops ci --check`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
