# Proposal

## Why

The stage job (#2654) writes a failing test as task `n.1` of every task group. This holds also for a group that changes no behavior: a document, a manifest, a workflow, or a deletion. The model must invent a "test" for such a group, and the implement job builds it. Issue #3005 reports the result: a contrived test for a deletion (#2175), and a scratch file that stopped the Job.

The owner set the rule on 2026-11-01: write tests for new code functionality. Every other change has a command or a repeatable process that verifies it. The rule follows behavior, not the path.

## What Changes

- `StageGroup` gets a `kind`: `behavior` or `other`.
- A `behavior` group has `test` and `verify`. `verify` runs the test. A `behavior` group must change a path under `src/`.
- An `other` group has no `test`. It has `verify` (one command that can run again) or `process` (the steps of a repeatable manual check).
- The validator refuses a `test` on an `other` group, a `behavior` group with no `test`, and a `behavior` group that changes no path under `src/`. The model gets the problem text and answers again.
- `group_text` renders task `n.1` as the failing test for `behavior`. It renders `n.1` as the work with its verification for `other`, with no text "fails on the base".
- `documentation` is `null` when the group changes no document. Then `group_text` renders no documentation task, so no task says "Change no document" and then runs the document generator.
- The stage prompt, the split prompt and the implement prompt follow the kind. A test fails if a prompt and the validator disagree on the kind names or on a field.
- `openspec/config.yaml`, AGENTS.md rule 4, `docs/TESTING.md` and `k8s/README.md` step 15 state the same rule.
- The change has a spec delta: the reply of the model and the text of `tasks.md` are observable behavior of `devops roadmap stage`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: a task group has a kind, the texts of its tasks, and a rendering by kind

## Impact

- Code: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`
- Prompts: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/ai/tasks/roadmap_stage_split.md`, `src/devops_cli/ai/tasks/roadmap_implement_step.md`
- Documents: `AGENTS.md`, `src/devops_cli/templates/AGENTS.md.j2`, `docs/TESTING.md`, `k8s/README.md`, `openspec/config.yaml`
- Tests: `tests/roadmap/test_roadmap_stage_kind.py`, `tests/roadmap/test_roadmap_stage_plan.py`, `tests/support/builders.py`

## Feasibility

- Checked on `origin/main` (4734035c). `StageGroup.test` is a required `Sentence` in `src/devops_cli/roadmap/stage_change.py`. `group_text` always renders ``{index}.1 {group.test}, and verify that `{group.verify}` fails on the base``. The prompt `roadmap_stage_change.md` says "`test`, the failing test to write first" and "Every group is written test first". So the cause in the issue is real.
- Counted the plans under `openspec/changes/` on `main` with a script that reads each `Changes:` line of `tasks.md`: 55 of 110 groups, in 26 plans, change no path under `src/`. The issue counted 50 groups in 22 plans on the same day, before later plans merged.
- Read the plans of #2175 (`openspec/changes/2175-the-five-functions-and-properties-that/tasks.md`) and #2162 (`openspec/changes/2162-mutation-runs-decide-which-of-the/tasks.md`). Both hold a contrived test task, as the issue says. The tests replay their shapes with the new kinds.
- The schema can hold the rule: `StageGroup` is a pydantic model with `model_validator`. `chat_structured` sends a reply that fails the schema back once with the field of each violation (`_REPLY_RETURNS`). So a violation gives the model the problem text with no new retry code.
- First checks of the implementation: `uv run devops ci test tests/roadmap/test_roadmap_stage_kind.py`, `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py`, `uv run devops ci test tests/invariants/test_change_folders.py`, `uv run devops ci test tests/invariants/test_agents_md_claims.py`.
- The tuicr line under "Workflow follow-up" stays. `tuicr` is in `tools.lock`, `docs/SDLC.md` documents the review round, and `openspec/config.yaml` allows the line. No invariant needs it, but it is not stale, and a removal is a different change.

## Existing Tool Considered

pydantic, which the project already uses for the reply schema. A `model_validator` states the rules of the kinds, and `chat_structured` already returns a failed reply to the model. No new library or parser is needed. The change deletes the always-required `test` and `documentation` fields of `StageGroup` and the fixed three-task text of `group_text`.
