# Tasks

## 1. Write the delivery metadata before the archived push

Reads: `src/devops_cli/roadmap/implement/implement_run.py`, `tests/roadmap/implement/test_roadmap_implement_job_scoped.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`, `tests/support/roadmap_implement.py`. Changes: `src/devops_cli/roadmap/implement/implement_run.py`, `tests/roadmap/implement/test_roadmap_implement_job_scoped.py`.

- [ ] 1.1 Write `test_a_scoped_check_that_fails_writes_the_delivery_metadata_before_the_push` and `test_the_delivery_metadata_is_written_once_for_one_pull_request` in `tests/roadmap/implement/test_roadmap_implement_job_scoped.py`, and watch them fail. The first seeds the staging title and the labels `type/docs` and `scope/openspec` on pull request 5, fails the pre-push hook for good, and answers the `git push` of the branch with a side effect that asserts `world.sent("PATCH", f"pulls/{PULL}")` already holds the delivery title and a body with `Closes #1`, and that the store's labels of pull request 5 are already the delivery ones. The second calls the helper twice and asserts one `PATCH` and one `label_issue` write
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job_scoped.py` fails on the base
- [ ] 1.2 Split `_pull_request` of `src/devops_cli/roadmap/implement/implement_run.py` into `_delivery_metadata` and the comment of the steps. `_delivery_metadata` sets the step `pull_request`, returns early when `self.pull` is None or when `self.metadata_written` is already that pull request, builds the change name from `_archived_name` and `_active_change`, sets the title and the body with `client.update_pull`, writes the labels through `add_pull_labels` and `remove_pull_labels`, and records the pull request it wrote. Call `self._delivery_metadata()` in `execute` after `self._finish_change()` and before `self._push()`. Keep `self._delivery_metadata()` and then `self._comment(pull, _NOTHING_YET)` in `_pull_request`. Add the field `metadata_written: int | None = None` to `_ItemRun` beside `pull`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job_scoped.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
