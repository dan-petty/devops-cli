# Design

## Context

Readiness reads the files of a pull request once (`pulls/{n}/files`) and judges grounding with a tuple of predicates, each of which returns one blocker or nothing. The task-file predicate was the last of them, and the base probe read `docs/agent/tasks` to decide whether grounding applies. See proposal.md for the motivation.

## Goals / Non-Goals

**Goals:**

- Replace the task-file predicate with two predicates over the same file list, and move the base probe to `openspec/changes`.
- Delete the task files and every reader of them in one pull request.

**Non-Goals:**

- Readiness does not judge whether a change is valid. The `openspec` row of `devops ci` does that, and its check run blocks through the check-run rule.
- Readiness does not convert or keep the old task files. Git history keeps them.

## Decisions

- **The archived folder has a grammar of its own.** `openspec/changes/archive/<YYYY-MM-DD>-<issue>-<slug>/<file>` is a second closed grammar beside the active one, `openspec/changes/<issue>-<slug>/<file>`. Both are in `config/constants.py` and both name the change in a `change` group. Rejected: one grammar for both, because the date prefix would make the active grammar read the year as the issue (ADR 0010).
- **"Adds" means the path is new in the head.** A file counts when GitHub reports it as `added`, `renamed` or `copied`. Rejected: the old set of `added`, `modified` and `renamed`. A `modified` file in an archived folder means that the base already holds that folder, so an earlier pull request archived the change. `openspec archive` writes a new dated folder each time.
- **The blocker names the change when the pull request has one.** When the pull request writes an active folder of its issue, the blocker names `openspec/changes/archive/<date>-<issue>-<slug>/` with that slug and the command `uv run devops openspec archive <issue>-<slug>`. Otherwise it names `<issue>-<slug>` as placeholders.
- **The specs and the archive have one writer.** A path in `openspec/specs/` is accepted only when the pull request adds its own archived folder. A path in `openspec/changes/archive/` is accepted only when it is in the archived folder of the issue that the pull request closes. This also stops a hand-run `openspec archive` or `openspec sync` in another pull request. A missing archive and an unwanted write are two blockers, because the fixes differ.
- **No read of `tasks.md`.** Rejected: the contents request that ADR 0010 planned for an unticked task. In a scratch repository, `openspec validate --archived` exited 1 on an archived change with an unticked task, and the `openspec` row runs that check on every pull request.
- **The decommission test does not name the deleted directory.** It builds `docs/agent/tasks` from its parts with `PurePosixPath`, so the scan of `tests/` does not find the test itself.

## Risks / Trade-offs

- [A pull request that is open when this change merges still adds a task file] → Readiness blocks it until it converts the task file into a change folder and archives it, and the decommission test fails while the task file is in the tree.
- [Two pull requests archive into one capability] → The second gets a text conflict in `spec.md` after the first merges, and its author resolves the conflict (ADR 0010).
- [A rename out of the archived folder of another issue shows only its new path] → `ChangedFile` keeps no previous path. Review catches this case, and the `openspec` row validates the archive.
