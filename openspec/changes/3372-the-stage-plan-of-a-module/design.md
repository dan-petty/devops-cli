# Design

## Decisions

- **Identify a move by the pair of an old path in `changes` and a new path under a subpackage in `creates`**: The reply already records a move that way, so the check needs no new field and no new schema rule.
- **Take the prefix from the old stem up to the first underscore**: The job modules of `src/devops_cli/roadmap/` are named `<prefix>_<name>.py`, such as `stage_ready.py`, so one rule finds every module of a prefix.
- **Require the missing modules in the group `changes` or in a later group `changes`**: A plan may split a large move over several groups, and the check must accept that order.
- **Refuse a `verify` literal that names one module of the prefix**: One sampled import passes while another module of the same prefix stays in place, which is the defect of #3372.
- **Run the rule in `check_proposal` and state it in the stage prompt**: The stage job and the replay both call `check_proposal`, so one rule judges both, and the prompt tells the planner the rule before it writes.

## Rejected alternatives

- **Add a `moves` field to the group schema**: The group already lists `changes` and `creates` in `src/devops_cli/roadmap/stage_change.py`, so a new field repeats data that the check reads.
- **Read the prefix from the group title**: `title` is free text of `StageGroup` in `src/devops_cli/roadmap/stage_change.py`, so a planner can omit the prefix from it.
- **Rely on the stage prompt alone**: A prompt cannot refuse a reply; `check_proposal` is the gate that the stage job and the replay call.
- **Verify a move with one `uv run pytest` command**: The rules of `src/devops_cli/ai/tasks/roadmap_stage_change.md` accept only `uv run devops` and the `! git grep` form as a `verify` command.
