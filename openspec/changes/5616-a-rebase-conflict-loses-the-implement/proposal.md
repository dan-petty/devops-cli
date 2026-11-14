# Proposal

## Why

An implement run loses every passed task group when `origin/main` changes a file that a group changed: the rebase of each `wip:` and checkpoint push conflicts, the job pushes nothing, and the pod ends with the work on an `emptyDir`, so a retry must build every group again (#5616).

## What Changes

- Push the unrebased head to the item branch with `--force-with-lease` when a `wip:`, checkpoint or stop push conflicts, and keep the run going.
- Write each conflicting path to `implement.conflict` at that push, open no pull request and skip the pre-push hook.
- Push the head and stop the item with the class `conflict` when the end push conflicts, so the branch keeps every passed group.
- Name each conflicting path, the item branch and the count of passed task groups in the comment of a conflict stop.
- State the conflict push, the record and the conflict stop in `docs/ROADMAP_WORKFLOW.md` and `docs/SDLC.md`.
- Rewrite the test that asserts a conflict pushes nothing, and add the checkpoint and end push conflict tests.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job/pull-request`: A conflict push keeps the work on the item branch, A conflict at the end push keeps the branch and stops, Each push holds the default branch unless its rebase conflicts
- `roadmap-implement-job/stops`: A conflict stop names the conflicted files

## Impact

- Code: `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`, `docs/SDLC.md`
- Tests: `tests/roadmap/implement/test_roadmap_implement_checkpoint.py`, `tests/roadmap/implement/test_roadmap_implement_push_current.py`

## Feasibility

- The probes confirm the paths that the plan changes: "The path `docs/TESTING.md` is a file of the staging commit.", "The path `src/devops_cli/roadmap/implement/implement_run.py` is a file of the staging commit." and "The path `src/devops_cli/roadmap/implement/git_isolation.py` is a file of the staging commit."
- The probe "`OriginGit` defines no field `push` in `src/devops_cli/roadmap/implement/git_isolation.py`." reports a method and no field: `src/devops_cli/roadmap/implement/git_isolation.py:def push` is that method, and it takes `lease`.
- The premise holds in the code: `src/devops_cli/roadmap/implement/implement_run.py:1937:tip = self._current_tip(in_step=in_step)` raises the conflict stop, and `src/devops_cli/roadmap/implement/implement_run.py:1944:except _StopError as exc:` turns it into the text of a failed push, so nothing reaches `origin`.
- The checkpoint makes no push after a conflict, because `src/devops_cli/roadmap/implement/implement_run.py:1159:if self.checkpoints_off or not self.passed:` reads the flag that a failed push sets.
- The conflict stop already names the class and the files: `src/devops_cli/roadmap/implement/implement_run.py:840:failure_class=FailureClass.CONFLICT,`, `src/devops_cli/roadmap/implement/implement_run.py:833:reason += texts.implement_stop_rebase_files.format(files=_files_lines(files))` and `src/devops_cli/roadmap/implement/implement_run.py:841:conflict_files=files[:CONST_ROADMAP_IMPLEMENT_REASON_PATHS],`.
- The stop takes a note only when it pushes, at `src/devops_cli/roadmap/implement/implement_run.py:1832:if stop.push and not note:` and `src/devops_cli/roadmap/implement/implement_run.py:1833:note = self._kept_note(branch=stop.kept_branch)`, and a conflict stop pushes nothing, so the comment names no branch and no count today.
- The record key exists at `src/devops_cli/roadmap/stores/store.py:388:CONFLICT = "implement.conflict"`, the stop writes it at `src/devops_cli/roadmap/implement/implement_run.py:1900:ImplementRecordKey.CONFLICT: json.dumps(list(stop.conflict_files))`, and the next Job clears it at `src/devops_cli/roadmap/implement/implement_run.py:745:marks[ImplementRecordKey.CONFLICT] = None`.
- The lease and the skipped hook are already in the one push, `src/devops_cli/roadmap/implement/git_isolation.py:def push`: `src/devops_cli/roadmap/implement/git_isolation.py:346:leased = [f"--force-with-lease={ref}:{lease}"] if lease is not None else []` and `src/devops_cli/roadmap/implement/git_isolation.py:348:folder.call("push", "--quiet", "--no-verify", *leased, self.url, f"{tip or ''}:{ref}")`.
- The plan names a count for the set of push paths that the rule covers: the tool `callers` gives three call sites of `_push_passed` in `src/devops_cli/roadmap/implement/implement_run.py`, at `src/devops_cli/roadmap/implement/implement_run.py:1161:if failed := self._push_passed():` for the checkpoint, at `src/devops_cli/roadmap/implement/implement_run.py:1201:if failed := self._push_passed(in_step=True):` for the `wip:` push of a step, and at `src/devops_cli/roadmap/implement/implement_run.py:1828:note = self._push_passed(at_stop=True) if stop.push else ""` for the stop. Each of the three is covered, and none is left out.
- The `wip:` push of a running step takes the same conflict stop from the copy, because `src/devops_cli/roadmap/implement/implement_run.py:1386:self._rebase(copy)` raises it and the checkout stays as it is.
- The count of passed groups is the number of task groups whose tasks are all ticked in the `tasks.md` of the item: `_groups` takes the first group that is not fully ticked at `src/devops_cli/roadmap/implement/implement_run.py:1100:group = next((g for g in tasks if not all(task.ticked for task in g.tasks)), None)` and records the passed group at `src/devops_cli/roadmap/implement/implement_run.py:1143:group=str(group.number),`. The count for an arbitrary item is unverified at plan time, because no tool of this run can count the groups of a change that no run has built; the behavior test of group 2 fixes it for a change of four groups whose first two are ticked.
- `OriginGit.push` at `src/devops_cli/roadmap/implement/git_isolation.py:def push` needs a network: it pushes to the URL of `origin`.
- `OriginGit.heads` needs a network, because it runs `ls-remote`, and `OriginGit.fetch` needs a network, because `_sync` fetches the default branch before each rebase.
- `_push_with_lease` needs a checkout of the repository, because it reads the remote tip of the clone at `src/devops_cli/roadmap/implement/implement_run.py:1350:remote = self._git("rev-parse", f"origin/{self.branch}")`.
- `_head` and `_git` need a checkout of the repository, and `kept_commits` needs one too, because `_kept_note` passes it `self._git`.
- `RoadmapStore.set_marks` and `_fresh` need a client of the GitHub API, because they read and write the issue body.
- `parse_task_groups` and `Path.read_text` need no network and no client: they read the `tasks.md` of the checkout.
- The verify programs are `uv run devops ci test` and `uv run devops ci docs`. `uv`, `python` and `pytest` are runner tools of the image, and `git` is an installed package of the image, so the tests run git for real. No scanner is needed, and each scanner stays `NOT_IN_RUNNER`. The pod settings `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `capabilities.drop: ALL`, `allowPrivilegeEscalation: false` and `seccompProfile: RuntimeDefault` apply.
- No new failure class and no new runner capability is needed: the class `conflict` is in the taxonomy, its action is `wait`, and the runner image holds `uv`, `python`, `devops`, `git` and `pytest`.
- The finding that group 1 names no existing test of the module is corrected: groups 1 and 2 read `tests/roadmap/implement/test_roadmap_implement_job.py`, which imports the module at `tests/roadmap/implement/test_roadmap_implement_job.py:32:from devops_cli.roadmap.implement.implement_run import apply_implement, raise_for_failed`.
- The findings on the two long requirement texts are corrected: the details moved into the scenarios, and both texts are now shorter than the 500-character limit.
- The findings on the four scenarios are corrected: the scenario "A stop" names the record in words and no code span, and the scenarios "The record holds the files until a retry", "A clear rule keeps the files" and "A secret in a path" name the job record and the masking in words, so each result stays assertable and no code span names a function or a file.
- The test that asserts the loss is `tests/roadmap/implement/test_roadmap_implement_push_current.py:170:def test_a_conflict_at_a_wip_push_and_at_the_stop_pushes_nothing(`, and group 1 rewrites it.
- `tests/support/roadmap_implement.py:def advance_main` moves `main` on the clone of the test through the real git of the run, so the tests need no network and no client of GitHub.
- The first checks on the real system are `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_checkpoint.py tests/roadmap/implement/test_roadmap_implement_push_current.py`, then `uv run devops ci docs`.
- The issue names #4713, #5023, #4957, #5547 and #5575, and this run made no GitHub read of them: not checked. The plan needs no item delivered first, because it changes only the push phase of `src/devops_cli/roadmap/implement/implement_run.py`.
- The pod log and the missing branch of #1928 in the issue body are GitHub data: not checked.

## Existing Tool Considered

Git is the open, maintained tool that covers the push and the lease: `src/devops_cli/roadmap/implement/git_isolation.py:def push` already runs `git push` with `--force-with-lease` and `--no-verify`. Git holds no rule to abort a rebase, push the unrebased head, record the conflict and stop the job, which is this repository's workflow code, so the change builds that rule in `src/devops_cli/roadmap/implement/implement_run.py`: 200k tokens and 2 hours to build, keep and fix it.

## Dependencies

None.
