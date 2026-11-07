# Design

## Decisions

- **Put the stale-command rule in `_delta_problems` under the gate `spec-delta` of `src/devops_cli/roadmap/stage/stage_change.py`.**: The rule judges the spec delta against the base specs, as `_duplicate_problems` does, so the stage job, the replay and `plan-recheck` run it through one gate that already exists.
- **Give `check_proposal` and `check_gates` an optional `requirement_texts` map from capability to requirement name and statement.**: The map keeps `requirements` for names, so the duplicate-name check and every caller stay as they are, and a caller with no texts skips the check.
- **Read the statements in `read_spec` of `src/devops_cli/roadmap/stage/stage_specs.py` and carry them on `BaseSpec`.**: The stage job already reads each base spec there, and a field with a default keeps the four-argument construction and `specs_at` callers working.
- **Extract a removed name from a code span that starts with `devops ` or with `--` in an added requirement whose text says MUST NOT or SHALL NOT.**: A requirement states a command in a code span, so a small regular expression finds the name with no model call and no CLI parser.
- **Refuse both an unmodified base requirement that names the removed name and a modified text that keeps it.**: A modified text that keeps the old name contradicts the removal in the archived spec, so checking only the unmodified requirements would miss it.
- **Put `specs` first in `_GROUPS` of `src/devops_cli/roadmap/stage/stage_references.py` and change the requirement that states the order of the groups.**: The cap takes files from the groups in that order, so the living spec of a renamed command survives the cap, and the living spec states the order that the code holds.
- **State the replay score before and after the change in one task and add no golden-set case.**: `docs/ROADMAP_WORKFLOW.md:313` asks for the score of the same model, and no golden-set case holds base requirement texts, so the score does not move.

## Rejected alternatives

- **Add the rule only to the stage prompt.**: The model can ignore a prompt rule, and `src/devops_cli/roadmap/stage/stage_change.py:def check_proposal` is the gate that refuses a bad reply before the replay.
- **Add the rule only to `src/devops_cli/roadmap/stage/stage_eval_gates.py`.**: The stage job calls `check_proposal` in `src/devops_cli/roadmap/stage/stage.py`, so a rule in the replay alone would not refuse a bad reply before the branch is written.
- **Read the base specs inside `check_proposal` from a checkout.**: `check_proposal` gets no repository root, and the replay of the golden set holds a thinned tree with no text of the base specs, as `docs/ROADMAP_WORKFLOW.md:311` states.
- **Change `requirements` to hold the text of each requirement.**: `_duplicate_problems` compares requirement names, and six callers pass names, so a change of the value breaks the duplicate-name check and each caller.
- **Ask a model to find the contradictory requirement.**: The gate runs in the stage job and in the replay with no model call, so a model call would make the answer differ between runs.
- **Detect a rename in the issue text inside `reference_answer`.**: `reference_answer` in `src/devops_cli/roadmap/stage/stage_references.py` receives the name and the `git grep` output only, so it reads no issue text.
