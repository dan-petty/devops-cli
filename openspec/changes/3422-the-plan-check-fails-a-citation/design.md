# Design

## Decisions

- **Put the citation rule in `check_proposal`, as a helper that it calls with a reader of the staged file.**: `check_proposal` runs on the staged tree and on the replay, and `content_problems` holds no tree and is called by the replay with no file text.
- **Give `check_proposal` an optional `read_text` callable that defaults to `None`, and judge no citation without it.**: The stage job passes the reader of its checkout, a test passes a dict lookup, and the replay of the golden set passes none, so its recorded plans keep passing.
- **Add the reader to `StagedTree` in `src/devops_cli/roadmap/stage_paths.py`, beside `read` and `callers`, and return `None` when the tree has no checkout.**: `StagedTree.read` already keeps the checkout, and `callers` already reads it, so one class holds every read of the staged commit and a tree built from a list of paths judges nothing.
- **Compare the cited text with the staged line as a substring, after white space is collapsed in both and backticks and one trailing period are stripped.**: A plan cites a fragment of a long line, so an exact match of the whole line would refuse a true citation.
- **Resolve a `path:def name` and a `path:class name` citation by searching the staged text for the definition at any line.**: A symbol citation stays true when the code moves, which is the defect that #3400 shows.
- **Scan `feasibility`, `why` and each line of `what_changes`, and no other field.**: These are the evidence fields that the issue names; a colon in `pull_request_body` or in a task text is not evidence.
- **State the rule in the stage prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md`.**: The planner reads only that prompt, so a check alone would keep refusing good plans after a move.

## Rejected alternatives

- **Put the rule in `content_problems`.**: `content_problems` holds no staged tree, and the replay of `docs/ROADMAP_WORKFLOW.md` calls it with no file text, so it would refuse good recorded plans.
- **Read the file from the working tree inside the check.**: The working tree is not the staged commit, and `tests/roadmap/test_roadmap_stage_content.py` builds a `StagedTree` from a list of paths with no checkout.
- **Extend `StagedTree` with a map of the text of every file.**: `src/devops_cli/roadmap/stage_paths.py` builds the tree before the reply is parsed, so the caller would read the paths twice; the change reads one cited file at a time instead.
- **Refuse a citation always, with no `read_text` callable.**: The replay of the golden set holds a thinned tree with no checkout, so it would refuse every good recorded plan.
- **Add the rule in `src/devops_cli/roadmap/stage_verify.py`.**: The verification pass runs after the plan is written, so a stale citation would already be in the change folder.
- **Report a stale citation as a warning only.**: The plan would still ship a false proof, which is the defect that #3400 shows.
