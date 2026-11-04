# Proposal

## Why

The implement job must stop an item whose delivery title the pull request form refuses (#3368). `_delivery_title` in `src/devops_cli/roadmap/implement_run.py` now calls `title_problems` and raises the stop, so both `_publish` and `_pull_request` refuse a bad title, and `_publish` checks the title before its first push. PR #3319 added that guard and one test, `test_a_title_that_the_check_refuses_stops_the_item_before_the_job_writes_it`, which covers a title with no Conventional Commit type on the path that updates an existing pull request. Two cases that #3368 names have no test: a type that the project does not declare, and the first push, where the job must stop before it pushes a branch. Without them, a change that moves the guard after the push, or that drops the type check, passes the suite.

## What Changes

- Add a test to `tests/roadmap/test_roadmap_implement_job.py` for an issue title `wip(cli): add a flag`, whose type `wip` the project does not declare: the job stops the item and writes no pull request title.
- Add a test for a Planned item whose delivery title has no type, with the title edited in the planned target because the plan judge already refuses such an issue title: the job stops before `_publish` pushes the branch, so `origin` holds no branch and no draft pull request exists.
- The change alters no behavior that a consumer observes, because it adds tests for behavior that `openspec/specs/roadmap-implement-job/spec.md` already states. It has no spec delta and sets `skip_specs: true`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Tests: `tests/roadmap/test_roadmap_implement_job.py`

## Feasibility

Confirmed on 2026-11-04 at `origin/main` (ecfc9b80).

- `git log -S "problems = title_problems" -- src/devops_cli/roadmap/implement_run.py` shows `be129c99` (`fix(roadmap): count the implement title like the CI check`), which added the guard to `_delivery_title` before #3368 was staged.
- `read_file` on `src/devops_cli/roadmap/implement_run.py` shows `_delivery_title` at line 957 running `title_problems(title, declared)` and raising `_StopError`, `_publish` at line 937 calling `_delivery_title` before `self._git("push", "-u", "origin", self.branch)` at line 938, and `_pull_request` at line 1005 calling `_delivery_title` before `client.update_pull` at line 1006.
- `read_file` on `tests/roadmap/test_roadmap_implement_job.py` shows the one #3319 test at line 265, which uses `job_world` and asserts an empty `PATCH pulls/<number>` for an issue title `Add a flag`.
- `grep` on `tests/support/roadmap_implement.py` shows the `planned_world` fixture at line 557, whose docstring says the change is on `main` and no branch and no pull request exist, so the first-push path is testable offline.
- `uv run devops ci test tests/roadmap/test_roadmap_implement_job.py` runs the module offline and needs no network.

## Existing Tool Considered

`title_problems` in `src/devops_cli/roadmap/pull_form.py` checks the form, the type, the scope and the summary length, and `_delivery_title` already calls it. This change builds no checker and no guard: it adds two tests that hold the existing guard in place. The cost is about 1,000 tokens of agent work and under ten minutes of elapsed time. The change deletes no internal code.
