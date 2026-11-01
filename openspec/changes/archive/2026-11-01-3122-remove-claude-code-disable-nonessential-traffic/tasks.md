# Tasks

## 1. Remove CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC

- [x] 1.1 Update `tests/core/test_third_party_telemetry.py` to assert that `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` is omitted from container environments
  - Verification: `uv run devops ci fail-to-pass --base origin/main`
- [x] 1.2 Remove the variable from `.devcontainer/devcontainer.json`
  - Verification: `uv run devops ci devcontainer`
- [x] 1.3 Remove the variable from `.devcontainer/image/devcontainer.json`
  - Verification: `uv run pytest tests/core/test_third_party_telemetry.py -k test_devcontainer_image_disables_telemetry`
- [x] 1.4 Remove the variable from `src/devops_cli/templates/devcontainer.json.j2`
  - Verification: `uv run pytest tests/core/test_third_party_telemetry.py -k test_a_rendered_devcontainer_template_omits_claude_code_nonessential_traffic`
- [x] 1.5 Update telemetry opt-out examples in `SECURITY.md`
  - Verification: `git grep "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"`

## 2. Verification and static checks

- [x] 2.1 Verify fail-to-pass against base tree
  - Verification: `uv run devops ci fail-to-pass --base origin/main`
- [x] 2.2 Run lint, format, typecheck, and telemetry tests
  - Verification: `uv run devops ci lint && uv run devops ci format --check && uv run devops ci typecheck && uv run pytest tests/core/test_third_party_telemetry.py`

## Workflow follow-up

- Pending a person: rebuild devcontainer to confirm remote sessions work without restriction.
