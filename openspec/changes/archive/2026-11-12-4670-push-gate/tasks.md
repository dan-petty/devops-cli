# Tasks

## 1. The pre-push hook

- [x] 1.1 Write the tests: a branch behind `main` is refused with the fix, a rebased branch passes, a tag and a run that is no push pass
  - Verification: `$ uv run devops ci test tests/git/test_branch_current_hook.py`
- [x] 1.2 Add the hook `branch-current` to `.pre-commit-config.yaml`, first in the pre-push stage, let the invariants of the hooks accept it, and let `devops ai agents` name it by its `id`
  - Verification: `$ uv run devops ci test tests/git/test_branch_current_hook.py tests/roadmap/test_roadmap_runner_tools.py tests/invariants/test_runner_hooks.py tests/invariants/test_workflow_contracts.py tests/commands/test_instruction_generator.py`

## 2. The implement Job

- [x] 2.1 Change the conflict tests: a conflict before the final push, after the fix step, at a `wip:` push and at the stop pushes nothing
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job.py tests/roadmap/implement/test_roadmap_implement_push_current.py tests/core/test_roadmap_implement_checks.py`
- [x] 2.2 Remove `push_on_conflict` from `_sync` and `_rebase`, and the push of the head from the conflict path of `_current_tip`
  - Verification: `$ uv run devops ci test tests/roadmap/implement tests/core/test_roadmap_implement_checks.py`

## 3. Documents

- [x] 3.1 Name the hook in `docs/SDLC.md`, `CONTRIBUTING.md`, ADR 0014 and the skill `devops-pr-ci`, and say in `docs/ROADMAP_WORKFLOW.md` that a conflict pushes nothing
  - Verification: `$ uv run devops ci --check --only docs,openspec`
