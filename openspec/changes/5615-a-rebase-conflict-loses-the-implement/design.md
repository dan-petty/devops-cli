# Design

## Decisions

- **Push the head without the rebase at a conflict of a checkpoint, a `wip:` or a stop push, and return no failure note from that push.**: The passed groups stay on `origin` behind a lease, and `_checkpoint` keeps its checkpoints, so a later group's commit still reaches `origin`.
- **Write the conflicting paths to `implement.conflict` from the conflict push, and keep them when a later stop holds none of its own.**: The record is the only durable trace of a conflict that pushes and keeps going, and the first record write of the next Job hands it to the first step of its run.
- **Keep `--no-verify` on every push and add no hook exception.**: `src/devops_cli/roadmap/implement/git_isolation.py:348:folder.call("push", "--quiet", "--no-verify"` shows that `OriginGit.push` bypasses the hook already, so a hook change adds nothing.
- **Keep the final push that conflicts pushing nothing, with the class `conflict` and the conflicting paths in its comment.**: The tests `test_a_conflict_on_the_rebase_before_the_push_pushes_nothing` and `test_a_conflict_on_the_rebase_before_the_push_names_the_conflicted_files` pin that stop, and a continuation or the fix-conflict step resolves the conflict on the pushed work.
- **Test offline with a real local clone and a local bare `origin`, and move `main` with the scripted effects.**: `docs/TESTING.md` forbids a network in a test, and the `JobWorld` fixtures already move the `main` of the local `origin` while a step runs.
- **Give the checkpoint test three task groups whose group 1 changes `CONTEXT.md`, and move `main` over `CONTEXT.md` before the checkpoint of group 2.**: Only a third group shows that the checkpoint after a conflicting checkpoint still pushes, which is the loss that the earlier plan caused, and `CONTEXT.md` is a file that the test clone and the staged commit both hold.
- **Leave `openspec/specs/roadmap-implement-job/pull-request/spec.md` to `openspec archive`, which writes it from the delta of this change.**: A task group never writes a living spec, and the delta renames and modifies the requirement that the archive writes.

## Rejected alternatives

- **Skip the conflict push, as the job does today.**: `src/devops_cli/roadmap/implement/implement_run.py:1162:self.checkpoints_off = True` leaves the pod's work tree as the only copy, so the item branch holds nothing and a retry builds every group again.
- **Return the conflict as a failure note after the head push, as the earlier plan did.**: `src/devops_cli/roadmap/implement/implement_run.py:1161:if failed := self._push_passed():` turns every later checkpoint off on a non-empty note, so the later groups' commits stay only in the work tree.
- **Push the head to a separate checkpoint branch.**: The continuation of a run takes the item branch from `origin`, so a separate branch keeps no work that the continuation reads.
- **Add `--no-verify` to the conflict push only.**: `src/devops_cli/roadmap/implement/git_isolation.py:348:folder.call("push", "--quiet", "--no-verify"` shows that every push already carries it.
- **Force-push the final head without the rebase.**: The issue asks to keep the pushed branch and stop, and a forced head meets the same conflict at its next push.

## Unchanged references

- `openspec/specs/roadmap-implement-job/pull-request/spec.md` (spec requirement): `openspec archive` writes this living spec from the delta of the change, and no task group edits it.
