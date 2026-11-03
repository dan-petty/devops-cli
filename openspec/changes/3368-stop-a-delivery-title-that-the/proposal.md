# Proposal

## Why

The implement job calls `delivery_title` and writes the result to GitHub with no check (#3368). A person can edit the issue title after staging, and the job then opens or rewrites a pull request whose title the `Semantic PR title` check refuses, after it has pushed a branch and spent tokens.

## What Changes

- `_publish` runs `title_problems` on the delivery title before `create_draft_pull`, and stops the item on a problem after it deletes the branch that this run pushed.
- `_pull_request` runs `title_problems` on the delivery title before `update_pull`, and stops the item on a problem.
- The stop message names each title problem and the issue title, and the job writes no pull request title.
- A new test module covers an edited issue title with no Conventional Commit type and one with an undeclared type.
- The spec delta adds the delivery title guard to the `roadmap-implement-job` capability, because the job's observable behavior on GitHub changes.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job`: A refused delivery title stops the item

## Impact

- Code: `src/devops_cli/roadmap/implement_run.py`
- Tests: `tests/roadmap/test_roadmap_implement_title.py`

## Feasibility

- `list_files` on `tests/roadmap` showed no `test_roadmap_implement.py`, and showed the implement tests split by subject, such as `tests/roadmap/test_roadmap_implement_pull.py`.
- The probe lines confirm the premise: `delivery_title` is defined at src/devops_cli/roadmap/implement_run.py:1005: delivery_title = self._delivery_title()` and `delivery_title` is defined at src/devops_cli/roadmap/stage_change.py:794:def delivery_title(issue_title: str, declared: Collection[str]) -> str:`
- `read_file` on `src/devops_cli/roadmap/implement_run.py` showed `_publish` calling `create_draft_pull` with the delivery title and `_pull_request` calling `update_pull` with it, and neither call runs a title check.
- `read_file` on `src/devops_cli/roadmap/pull_form.py` showed that `title_problems(title, declared)` checks the form, the declared type, the declared scope and the summary length, so the issue needs no new checker.
- `search_code` for `title_problems` in `src/` showed the one definition in `src/devops_cli/roadmap/pull_form.py` and its caller on the `pr create` path, and no caller in `src/devops_cli/roadmap/implement_run.py`.
- The issue names `tests/roadmap/test_roadmap_implement.py`, which no commit ever held, so the two tests go in a new module `tests/roadmap/test_roadmap_implement_title.py` that mirrors `src/devops_cli/roadmap/`.
- First checks against the real system: `uv run devops ci test tests/roadmap/test_roadmap_implement_title.py`, then `uv run devops ci test tests/roadmap/test_roadmap_implement_pull.py` to show both write paths still pass.

## Existing Tool Considered

The repository already holds the checker: `title_problems` in `src/devops_cli/roadmap/pull_form.py` checks the form, the declared Conventional Commit type, the declared scope and the summary length, and `devops pr create` calls it. The change builds no replacement and adds one call at each of the two write sites, about 15 lines and two tests. The cost is about 15k tokens of agent work and under an hour of elapsed time. The change deletes no internal code.
