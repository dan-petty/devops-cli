# Design

## Decisions

- **One helper, `_delivery_metadata`, writes the title, the body and the labels, and `_pull_request` calls it and then posts the comment of the steps.**: The Staged path and the Planned path need the same metadata, and two copies can drift. The comment of the steps is no metadata and stays where the steps end.
- **`execute` calls the helper after `_finish_change` and before `_push`.**: `_scoped_checks` runs inside `_push` and a failure there stops the item with `kept_branch`, which pushes. Writing before `_push` covers that stop and the normal push with one call.
- **The helper is idempotent for one pull request: it records the pull request it wrote and returns at once on a second call.**: A Staged item calls it twice, once in `execute` and once in `_pull_request`, and the run must send one `PATCH` and one label write.
- **The helper returns early when `self.pull` is None.**: A Planned item has no pull request until `_publish` creates it inside `_push`, so the first call has nothing to write and `_pull_request` writes the final body and the labels.
- **A stop before the archive keeps the staging form.**: The change folder is still active, so the plan-check reads a plan pull request with a plan title, and the archived commit is not on the branch.
- **A refused title or body stops the item before the push instead of after it.**: `_delivery_title` and `_body` raise `_StopError` with `push=False`, so the branch keeps the staging form only while nothing is pushed.

## Rejected alternatives

- **Move the `_pull_request(pull)` call before `_push()` and leave it there only.**: `_publish` sets `self.pull` inside `_push` (`src/devops_cli/roadmap/implement/implement_run.py:1162: self.pull = created.number`), so a Planned item has no pull request before the push. The comment of the steps also has to follow the push.
- **Write the metadata only in `stop`.**: The normal path pushes in `_push` (`src/devops_cli/roadmap/implement/implement_run.py:1071: self._push_with_lease()`) with no stop, and a Staged item's staging pull request needs the delivery form before that push.
- **Write the metadata again in `_push_passed` before it pushes.**: `_scoped_checks` runs inside `_push` (`src/devops_cli/roadmap/implement/implement_run.py:1067: self._scoped_checks()`), which `execute` reaches only after the helper call, so every stop with `stop.push` after the archive already holds the metadata and a second call proves nothing.
- **Send the title and body without reading the pull request first.**: `stale_labels(before.labels, old, new)` needs the labels of the pull request (`src/devops_cli/roadmap/implement/implement_run.py:1248: remove_pull_labels(self.store, pull, stale_labels(before.labels, old, new))`), so the staging `type/docs` and `scope/openspec` labels cannot be removed without the read.
- **Check the current title through `get_pull` and skip the write when it already matches.**: `PullRequest` holds no body (`src/devops_cli/github/client.py:60:class PullRequest(BaseModel):`), so a title comparison cannot prove that the body is in delivery form.
- **Assert the order of the metadata write and the push from the request log alone.**: The label writes go to the store through `label_issue` and `unlabel_issue` (`tests/support/fakes/roadmap_store.py:552: def label_issue(self, number: int, label: str) -> None:`), and git runs for real, so the order is asserted by a side effect on the `git push` call, as `move_main_when` does at `tests/support/roadmap_implement.py:456:def move_main_when(`.
