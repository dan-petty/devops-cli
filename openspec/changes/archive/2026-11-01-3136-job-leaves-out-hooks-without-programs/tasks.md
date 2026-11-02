# Tasks

## 1. Leave out a hook whose program is missing

Reads: `src/devops_cli/roadmap/implement_hooks.py` lines 60 to 100, `src/devops_cli/roadmap/runner_tools.py` lines 160 to 200, `.pre-commit-config.yaml` lines 95 to 120. Changes: `src/devops_cli/roadmap/runner_tools.py`, `src/devops_cli/roadmap/implement_hooks.py`, `tests/roadmap/test_roadmap_implement_hooks.py`, `tests/roadmap/test_roadmap_runner_tools.py`.

- [x] 1.1 Write the tests first, and verify that `uv run devops ci test tests/roadmap/test_roadmap_implement_hooks.py tests/roadmap/test_roadmap_runner_tools.py` fails before the code exists
- [x] 1.2 Add `HOOK_PROGRAMS` and `hooks_without_programs` to `runner_tools.py`, and make `trusted_config` leave those hooks out of its copy
- [x] 1.3 Verify with `uv run devops ci test tests/roadmap` and with `uv run pre-commit validate-config` on a copy written from `.pre-commit-config.yaml` without the hook

## 2. After the merge

- Pending a person: none. The next item that changes a workflow file shows the effect in its Job log.
