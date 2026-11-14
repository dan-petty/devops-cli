# Proposal

## Why

A rebase conflict at a checkpoint or wip push loses every passed group of an implement run (#5615): the job pushes nothing, the pod keeps its work tree on an emptyDir volume, and the item branch on origin holds nothing, so a retry builds every group again. The change keeps the head on the item branch.

## What Changes

- A checkpoint, `wip:` or stop push whose rebase conflicts aborts the rebase and pushes the head of the checkout to the item branch with a lease, so every passed group stays on `origin`.
- That push returns no failure note, so the job keeps its checkpoints and the commit of a later group still reaches `origin`.
- The conflicting paths go to `implement.conflict`, and a later stop keeps them when it holds none of its own.
- The final push that conflicts pushes nothing, keeps the item branch on `origin`, and stops the item with the class `conflict` and the conflicting paths in its comment.
- `docs/ROADMAP_WORKFLOW.md` and `docs/SDLC.md` state the new rule.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job/pull-request`: A conflicting push keeps the head on the item branch, A push rebases onto the default branch

## Impact

- Code: `src/devops_cli/roadmap/implement/implement_run.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`, `docs/SDLC.md`
- Tests: `tests/roadmap/implement/test_roadmap_implement_push_current.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`

## Feasibility

- `read_file` of `src/devops_cli/roadmap/implement/implement_run.py` lines 1156 to 1203 showed the loss: the checkpoint, the `wip:` push and the stop push all call `_push_passed`, and a rebase conflict returns a note instead of pushing.
- `src/devops_cli/roadmap/implement/implement_run.py:1161:if failed := self._push_passed():` turns the checkpoints off on any non-empty note, so the conflict push must return an empty note and the record must carry the conflict.
- `src/devops_cli/roadmap/implement/implement_run.py:1945:return texts.implement_stop_push_failed.format(output=mask_secrets(exc.reason))` is the old conflict result; the change replaces it with the head push, the record write and an empty note.
- `src/devops_cli/roadmap/implement/implement_run.py:1832:if stop.push and not note:` adds the kept-work note only when the stop push returned no note, so the empty note makes a stop name the branch and its last commit.
- `src/devops_cli/roadmap/implement/implement_run.py:1900:ImplementRecordKey.CONFLICT: json.dumps(list(stop.conflict_files))` writes only the files of the stop; the plan writes `stop.conflict_files or self.conflict_files`.
- `_push_passed` has three call sites: `src/devops_cli/roadmap/implement/implement_run.py:1161:if failed := self._push_passed():` at a checkpoint, `src/devops_cli/roadmap/implement/implement_run.py:1201:if failed := self._push_passed(in_step=True):` at a `wip:` push and `src/devops_cli/roadmap/implement/implement_run.py:1828:note = self._push_passed(at_stop=True) if stop.push else ""` at a stop. The final push is `_push`, which calls `_sync` and `_push_with_lease` directly, so it is not among them.
- `src/devops_cli/roadmap/implement/git_isolation.py:348:folder.call("push", "--quiet", "--no-verify", *leased, self.url, f"{tip or ''}:{ref}")` shows that every push already bypasses the pre-push hook and carries the lease, so the plan adds no `--no-verify` and no hook exception.
- `src/devops_cli/roadmap/implement/implement_run.py:1349:tip = tip or self._head()` is `_push_with_lease`, which the conflict push reuses; it needs a checkout of the clone and a network to the URL of `origin`, and the test gives both with the local bare `origin` of `StageRepo`.
- `_publish` needs a checkout of the clone, a network to `origin` and a client of GitHub to open the draft pull request, which the test answers with `GitHubApiFake`; `self.store.set_marks` needs a client of the roadmap store, which the test gives with `InMemoryRoadmapStore`; `_sync`, `_rebase` and `kept_commits` need a checkout, which the test owns under `tmp_path`.
- The plan relies on `src/devops_cli/config/constants.py:3547:CONST_ROADMAP_IMPLEMENT_REASON_PATHS: Final[int] = 20`, the bound that `src/devops_cli/roadmap/implement/implement_run.py:841:conflict_files=files[:CONST_ROADMAP_IMPLEMENT_REASON_PATHS],` applies; the plan adds no constant and no new bound.
- The probes confirm the cited paths: "The path `docs/TESTING.md` is a file of the staging commit." and "The path `tests/roadmap/implement/test_roadmap_implement_job.py` is a file of the staging commit."
- `docs/ROADMAP_WORKFLOW.md:412:A rebase conflict pushes nothing (#4670)` and `docs/SDLC.md:321:The implement Job installs no git hook: it rebases before each push and pushes nothing after a rebase conflict.` are the two rules that group 2 replaces.
- `tests/support/roadmap_implement.py:299:("write_file", {"path": "CONTEXT.md", "content": SHOUT_DOC}),` and `tests/support/roadmap_implement.py:535:def advance_main(world: JobWorld, name: str = "main-moved.txt", text: str = "Main.\n") -> None:` show that the clone of a test world holds `CONTEXT.md` and that `advance_main` writes a path on `main`, so the checkpoint test conflicts on `CONTEXT.md`, a file of the staged commit.
- The first checks against the real system are `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job.py tests/roadmap/implement/test_roadmap_implement_push_current.py`, then `uv run devops ci docs`.
- Every verify runs `uv`, `python`, `pytest` and `devops`, each a runner tool of the image; the plan starts no `kubectl`, `gh`, `docker` or scanner, and `kubectl` is `NOT_IN_RUNNER`.
- The stop class is `conflict`, which the failure taxonomy holds with the action `wait`; a failed test is the class `test`.
- The pod settings of the runner apply to the test run: `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `capabilities.drop: ALL`, `allowPrivilegeEscalation: false` and `seccompProfile: RuntimeDefault`.
- The probes say "`emptyDir` has no definition at the staging commit." The runner pod keeps its home on an `emptyDir` volume, which `k8s/devops/cronjob-runner.yaml` holds.
- `find_issues` with "rebase conflict implement push" listed an open issue #5616 with the same title as this one, so the change delivers it too and a person closes one of the two.

## Existing Tool Considered

No open, maintained library covers the rebase-conflict recovery of the roadmap implement step: devops-cli runs git through its own process seam in `src/devops_cli/roadmap/implement/git_isolation.py`, so the change edits `src/devops_cli/roadmap/implement/implement_run.py`. Cost: about 40k tokens to build, about 10k tokens a year to keep, about 20k tokens to fix a miss, and about 3 hours of elapsed work.

## Dependencies

None.
