# Proposal

## Why

A stopped implement run pushes the archived change commit while the pull request still holds the staging title, body and labels, so `Plan Check` and `devops pr check-readiness` fail on a pull request whose change is already archived (#3991). The pull request must hold the delivery form before the archived commit reaches `origin`.

## What Changes

- Add `_delivery_metadata` to `src/devops_cli/roadmap/implement/implement_run.py`: it sets the delivery title, the body that closes the issue and the labels of that title, and it returns at once for a pull request it has already written.
- Call `_delivery_metadata` in `execute` after `_finish_change` and before `_push`, so the Staged path writes the delivery form before the scoped checks and the push.
- Keep the `_delivery_metadata` call in `_pull_request` for a Planned item, whose pull request exists only after `_publish` creates it, and keep the comment of the steps there, after the push.
- Add `test_a_scoped_check_that_fails_writes_the_delivery_metadata_before_the_push` to `tests/roadmap/implement/test_roadmap_implement_job_scoped.py`: the side effect of the `git push` asserts that the delivery title, the closing body and the delivery labels are already there.
- Add `test_the_delivery_metadata_is_written_once_for_one_pull_request` to the same file: two calls send one `PATCH` and one label write.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job`: The job rewrites the pull request after the push

## Impact

- Code: `src/devops_cli/roadmap/implement/implement_run.py`
- Tests: `tests/roadmap/implement/test_roadmap_implement_job_scoped.py`

## Feasibility

- The probe says of the class that the issue cites: `ImplementRun` has no definition at the staging commit. No commit in the history added or removed its text. `search_code` with `ImplementRun` returned no match; the class of the run is `_ItemRun` at `src/devops_cli/roadmap/implement/implement_run.py:459:class _ItemRun:`. The name in the issue is wrong, and the code it describes is there.
- The issue names `_end()`. No such method exists: the stop path is `src/devops_cli/roadmap/implement/implement_run.py:1485: def end_stopped(self, stop: _StopError) -> _Ended:`, which calls `:1499: def stop(self, stop: _StopError) -> None:`, whose first line is `:1502: note = self._push_passed() if stop.push else ""`.
- `read_file` of `execute` showed the order that the issue reports: `src/devops_cli/roadmap/implement/implement_run.py:617: self._finish_change()`, then `:619: pull = self._push()`, then `:620: self._pull_request(pull)`. The archive comes first, the push second, and the metadata write third.
- `_push` runs the scoped checks before it pushes: `src/devops_cli/roadmap/implement/implement_run.py:1067: self._scoped_checks()`. `_scoped_checks` marks the stop as keeping the branch (`:1101: stop.kept_branch = True`), and `stop` then calls `_push_passed`, which pushes with a lease at `:1593: self._push_with_lease()`. So the archived commit reaches `origin` before `_pull_request` runs, which is the premise of the issue.
- `search_code` with `_pull_request(` returned the definition at `:1220` and one call site at `:620`, so no other path writes the metadata today.
- The staging title is in the fake at `tests/support/roadmap_implement.py:105: "title": "docs(openspec): plan #1 Stop the job dropping a comment"`, and the fake's labels are empty at `tests/support/roadmap_implement.py:108: "labels": [],`. A test that needs the staging labels seeds them, as `tests/roadmap/implement/test_roadmap_implement_job.py:1351: route_pull_status(job_world.api, status)` and `:1354: update={"labels": ("type/docs", "scope/openspec", "scope/ai")}` show.
- The label writes go to the store, not to the REST fake: `src/devops_cli/roadmap/implement/implement_run.py:1247: add_pull_labels(self.store, pull, new.labels)` and `:1248: remove_pull_labels(self.store, pull, stale_labels(before.labels, old, new))`, which call `label_issue` and `unlabel_issue` of `tests/support/fakes/roadmap_store.py`. A test reads them from `job_world.store._roadmap.issues[PULL].labels` and from `job_world.store._roadmap.job_writes`, as `tests/roadmap/implement/test_roadmap_implement_job.py:1360: assert set(job_world.store._roadmap.issues[PULL].labels) == {` does.
- The title and body write is the REST request that the fake records: `src/devops_cli/roadmap/implement/implement_run.py:1241: client.update_pull(self.repo, pull, title=delivery_title, body=body)`, read through `tests/support/roadmap_implement.py:528: def sent(self, method: str, tail: str) -> list[dict[str, Any]]:`.
- `_body` already closes the issue: `src/devops_cli/roadmap/implement/implement_run.py:1211: return build_body(why=self._why(change, room), issue=self.number, change=change)`.
- The plan-check job needs no change of its own: its condition at `.github/workflows/pr-title.yml:102: if: "${{ always() && github.event.pull_request.user.login == 'devops-cli-service[bot]' && startsWith(github.event.pull_request.title, 'docs(openspec): plan #')"` is false once the title is the delivery form, so the job is skipped and reports Success.
- Precondition of `get_github_session()`: a client of the GitHub service, which `tests/support/fakes/github.py` answers at the REST edge.
- Precondition of `client.get_pull`, `client.update_pull`, `client.comment_on_pull`, `add_pull_labels` and `remove_pull_labels`: a client of the GitHub service, answered by the fake and by the in-memory store.
- Precondition of `_archived_name`, `_active_change`, `_delivery_title`, `_body`, `declared_labels` and `title_labels`: a checkout of the repository, which the `job_world` fixture gives at `tests/support/roadmap_implement.py:608:def job_world(`.
- First checks against the real system: `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job_scoped.py`, then `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job.py`.
- The rejected plan's first point holds: the fixture's labels are empty, so the test seeds the staging labels on pull request 5 and routes them, as the existing label test does. The new plan names that seed and reads the labels from the store.
- The rejected plan's second point holds: with the write in `execute` before `_push`, a scoped-check stop already holds the metadata, so the new plan drops the `_push_passed` call and writes in `execute` only, plus the Planned path in `_pull_request`.
- The rejected plan's third point holds: `The pull request gets the labels of the new title` already covers the label replacement, so the modified requirement no longer restates it and adds no label scenario.
- The rejected plan's fourth point holds: the labels live in the store, so the new scenario says the pull request holds the delivery labels, and no scenario says the REST fake records a label write.

## Existing Tool Considered

No open, maintained tool covers the order of devops-cli's own archive, push and pull request update steps. The GitHub CLI edits a title, a body and labels, but it cannot make `_ItemRun` write them after the archive and before every push of an archived change. The change builds that order: 10000 tokens to build the code, 4000 tokens a year to keep and fix it, and 4 hours of elapsed time.

## Dependencies

None.
