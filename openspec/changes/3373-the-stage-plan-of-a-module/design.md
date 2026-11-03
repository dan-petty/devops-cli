# Design

## Decisions

- **Carry the reference hits in a structured `references` list of `StageProposal`, not in the design prose.**: A field is exact, and `check_proposal` reads the same reply that the job and the replay read, with no git call.
- **Hold the path, the kind, the `unchanged` flag and the reason in one `StageReference` entry.**: One entry keeps a reference and its decision together, so the two cannot disagree.
- **Render each unchanged reference with its path and reason in `_design_file`.**: The design then shows why a hit stays, and a test can assert the rendered text.
- **Give a reason the schema of a non-blank text when `unchanged` is true.**: A validator refuses an unchanged reference with no reason before the files are written.
- **Keep `references` empty when a plan moves no module.**: An empty list adds no problem, so a plan that moves nothing passes the same check.

## Rejected alternatives

- **Re-run `git grep` inside `check_proposal` to find the hits.**: The replay `uv run devops roadmap eval stage --replay` calls `check_proposal` and reads no git, so a git call in the gate would fail on a recorded plan.
- **Read the unchanged references from the free text of `feasibility` or of a decision.**: `feasibility` and `decisions` are free-form `Line` texts in `src/devops_cli/roadmap/stage_change.py`, so a path in them is easy to miss and hard to check.
- **Keep the import-only rewrite and trust the implement step to fix the broken strings.**: The issue states that a string does not follow an import, and the five snapshot files and the 37 quoted targets would fail after the move.
- **Add a new AST scanner for module references.**: An AST scanner misses string literals and snapshot paths, and it adds code to build and keep, while `reference_answer` already returns them.
