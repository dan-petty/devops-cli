# Design

## Decisions

- **Scan the work texts of the reply for a deletion verb and a guard target, and do not trust a flag that the model sets.**: A model that forgets a `deletes_check` flag passes the check, so the guard would be no guard. The scan is deterministic, as ADR 0005 asks of a finding.
- **The deletion verbs are `delete`, `remove` and `drop`, with the forms `deletes`, `deleted`, `removes`, `removed`, `drops` and `dropped`, matched without case and as whole words.**: The issue names these verbs, and a task writes `removes` or `removed`, so the exact words of the issue would miss a task. A `drop` form takes a doubled `p`, and a whole-word match keeps `remote` out of the result.
- **The guard targets are a `tests/` path, a `test_*` name and a `CONST_*` name.**: Each target is the form that the two changes of PR #3277 delete: a test function and an entry of a `CONST_*` inventory.
- **The scanned texts are `what_changes`, each group's `implementation` and `documentation`, and each decision with its reason.**: These are the texts that state the work of a plan, as the stage prompt and the group schema already define them.
- **A `weakened_checks` entry holds three required texts: `check`, `stopped` and `safeguard`.**: The issue asks for the check, what it stopped and the safeguard, and a reviewer reads each as a separate fact. One free text would let a plan skip the safeguard.
- **The planner prompt names the `weakened_checks` key and its rule, and the prompt-rules test checks the key against the schema.**: `roadmap_stage_change.md` is the only copy of the reply keys that the model reads. `tests/roadmap/test_roadmap_stage_prompt_rules.py` compares its top-level key bullets with the properties of the schema of `StageProposal`, so a key without its bullet fails the suite.
- **An entry satisfies a detected deletion when its `check` text holds the detected name or path.**: The match is deterministic, and a plan that deletes two checks needs two entries. A sentence that names the check still counts.
- **`render_change` writes `## Weakened checks` after `## Impact` and before `## Feasibility`, and only when the list is not empty.**: The proposal states what the change gives up, so a reviewer sees the weakened threshold beside the impact. A plan that weakens nothing keeps its file unchanged.
- **The new problem text lives in `MESSAGES.roadmap`, and the writer uses the section texts that #3490 put there.**: Every text of `stage_change.py` uses that namespace, and one text of the form holds the writer and the reader together.
- **The change carries an ADDED requirement in the capability `roadmap-stage/plan-text`.**: The stage job's answer to a plan is observable, so the change is no test, document or refactor and the config asks for a delta.

## Rejected alternatives

- **Require the model to set a `deletes_check` boolean on the reply.**: A model that forgets the flag passes the check, so the guard is no guard. `docs/adr/0005-review-findings-come-from-tools-not-models.md` asks a finding to come from a check and not from a model's claim.
- **Refuse every plan that lists a path under `tests/` in `changes`.**: `src/devops_cli/roadmap/stage_change.py` holds groups that add a test module in `creates`, so a plan that adds or edits a test without deleting one would be refused.
- **Match any word that means a removal, such as `strip` or `erase`.**: A synonym list grows without bound and refuses plans that delete nothing, while the issue names `Delete`, `Remove` and `drops`.
- **Let any non-empty `weakened_checks` entry satisfy every deletion.**: One entry would cover an unrelated deletion, so a plan could delete a second check with no record of it.
- **Write the section in `design.md` instead of `proposal.md`.**: `src/devops_cli/roadmap/stage_change.py` renders a design as decisions and rejected alternatives. A weakened threshold is a fact of the change that a reviewer must see beside its impact.
- **Keep only the check and write no section.**: The issue asks the plan for an entry that a person reads, and a refusal with no rendered text leaves the reviewer the same reading task.
- **Set `skip_specs: true`.**: `check_proposal` decides whether the stage job accepts a plan, so a consumer observes the change and `openspec/config.yaml` asks for a delta for it.
