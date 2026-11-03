# Tasks

## 1. Add the prompt-key gate to the stage gate set

Reads: `src/devops_cli/roadmap/stage_eval_gates.py`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`. Changes: `src/devops_cli/roadmap/stage_eval_cases.py`, `src/devops_cli/roadmap/stage_eval_gates.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_eval_gates.py`.

- [ ] 1.1 In `tests/roadmap/test_roadmap_stage_eval_gates.py`, assert that `gate_for(DefectType.PROMPT_KEY_MISSING)` is `GateName.PROMPT_KEYS`, that the gate refuses a plan whose group adds a field to `StageProposal` and changes no prompt reply key, and that the gate accepts the plan when a group changes `src/devops_cli/ai/tasks/roadmap_stage_change.md` with the reply key and its rule
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_gates.py` fails on the base
- [ ] 1.2 Add `PROMPT_KEY_MISSING = "prompt_key_missing"` to `DefectType` and `PROMPT_KEYS = "prompt_keys"` to `GateName` in `src/devops_cli/roadmap/stage_eval_cases.py`. Add `_prompt_key_gate` to `src/devops_cli/roadmap/stage_eval_gates.py`: it reads the groups that change `src/devops_cli/roadmap/stage_change.py` and whose title, implementation or documentation names `StageProposal` with a new field, and it returns one problem when no group changes `src/devops_cli/ai/tasks/roadmap_stage_change.md` with the reply key. Add `Gate(GateName.PROMPT_KEYS, "#3328", DefectType.PROMPT_KEY_MISSING, _prompt_key_gate)` to `GATES`. Add the message to `src/devops_cli/lang/en/messages.py`; it names the prompt file and the reply key. Run the gate in the stage job through `run_gates`, so a plan with the defect returns to the model once
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_gates.py` passes

## 2. Record the missing prompt key in the golden set

Reads: `src/devops_cli/roadmap/stage_eval_cases.py`, `src/devops_cli/roadmap/stage_eval_gates.py`, `tests/roadmap/test_roadmap_stage_eval_gates.py`. Changes: `tests/fixtures/roadmap_eval/stage/3328-missing-prompt-key/case.json` (new), `tests/fixtures/roadmap_eval/stage/3328-missing-prompt-key/issue.txt` (new), `tests/fixtures/roadmap_eval/stage/3328-missing-prompt-key/plan.json` (new), `tests/fixtures/roadmap_eval/stage/3328-missing-prompt-key/facts.json` (new).

- [ ] 2.1 Add the case folder `tests/fixtures/roadmap_eval/stage/3328-missing-prompt-key/`. Its `plan.json` holds one group that changes `src/devops_cli/roadmap/stage_change.py` and names a new field of `StageProposal`, and no group that changes `src/devops_cli/ai/tasks/roadmap_stage_change.md`. Its `case.json` holds one defect of the type `prompt_key_missing` with the gate `prompt_keys` and the message that names the prompt file. Its `facts.json` holds the tracked files that the gates need, and its `issue.txt` the body of this item
  - Verification: `uv run devops roadmap eval stage --replay` passes

## 3. State the prompt-key rule in the project documents

Reads: `AGENTS.md`, `docs/TESTING.md`, `openspec/config.yaml`. Changes: `docs/TESTING.md`.

- [ ] 3.1 Add one sentence to `docs/TESTING.md` that a plan which adds a field to `StageProposal` changes the reply-key bullets and the rule in `src/devops_cli/ai/tasks/roadmap_stage_change.md`, and that the `prompt_keys` gate refuses a plan that leaves the update out
  - Verification: `uv run devops ci docs` passes
- [ ] 3.2 Add the sentence to `docs/TESTING.md` beside the rules of a staged plan, and run `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs` passes

## Criteria

- Group 1: A test asserts that a plan adding a field to `StageProposal` without updating the prompt reply keys is refused with an informative message.
- Group 1: A plan adding a field to `StageProposal` that specifies both the prompt key bullet and the prompt rule passes the check.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
