# Design

## Decisions

- **Carry the reference hits in a structured `references` list of `StageProposal`, not in the design prose.**: A field is exact, and `check_proposal` reads the same reply that the job and the replay read, with no git call.
- **Hold the path, the kind, the `unchanged` flag and the reason in one `StageReference` entry.**: One entry keeps a reference and its decision together, so the two cannot disagree. The kind is a short text such as `quoted target`, `logger name` or `snapshot file`, and the design shows it beside the path.
- **Identify a moved module by the pair of an old `.py` path in `changes` and a new path in `creates`.**: The reply already records a move that way, so the check needs no new field and no new schema rule. The dotted name is the old path without `src/` and `.py`, with each `/` as a `.`, and the job skips a test module and `conftest.py`.
- **Probe the hits in the job after the reply and give them to `check_proposal`, not from the reply's list alone.**: The `references` tool keeps at most 60 files, and a move of `src/devops_cli/roadmap/` names 173, so a list that comes from the tool alone cannot show every hit. It also lets a reply leave a hit out. `reference_files` reads every hit from the staging commit with no cap, and the replay reads the recorded hits.
- **Render each unchanged reference with its path, its kind and its reason in `_design_file`.**: The design then shows why a hit stays, and a test can assert the rendered text.
- **Give a reason the schema of a non-blank text when `unchanged` is true.**: A validator refuses an unchanged reference with no reason before the files are written.
- **Keep `references` empty when a plan moves no module.**: An empty list adds no problem, so a plan that moves nothing passes the same check.
- **For a move by name prefix, verify the old dotted prefix and not one module's dotted name.**: `devops_cli.roadmap.` covers every module of the move and names no module, so it agrees with the rule of #3372, which refuses a literal that equals one module's import path.

## Rejected alternatives

- **Trust the reply's `references` list as the set of hits.**: A reply can leave a hit out, and the tool keeps at most 60 files while the motivating move names 173, so the check would accept a plan that misses most of the work.
- **Re-run `git grep` inside `check_proposal` to find the hits.**: The replay `uv run devops roadmap eval stage --replay` calls `check_proposal` and reads no git, so a git call in the gate would fail on a recorded plan. The job probes the hits and passes them, and the replay reads the recorded hits.
- **Read the unchanged references from the free text of `feasibility` or of a decision.**: `feasibility` and `decisions` are free-form `Line` texts in `src/devops_cli/roadmap/stage_change.py`, so a path in them is easy to miss and hard to check.
- **Keep the import-only rewrite and trust the implement step to fix the broken strings.**: The issue states that a string does not follow an import, and the five snapshot files and the 37 quoted targets would fail after the move.
- **Add a new AST scanner for module references.**: An AST scanner misses string literals and snapshot paths, and it adds code to build and keep, while `reference_answer` already returns them.
- **Verify one module's dotted name on a move by name prefix.**: #3372 refuses a `! git grep` literal that equals the import path of one module of a moved prefix, so `devops_cli.roadmap.stage_ready` cannot be the verification of that move.
