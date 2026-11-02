# Proposal

## Why

Every retry of a step uses the same model tier, so a model-specific defect fails the same call on every repeat and a harder step gets no stronger model (#3060).

## What Changes

- Add a config setting that maps each step class (plan, edit, repair, review) to an ordered list of tiers, one per attempt, defaulting to local tiers only.
- Print the ladder in the output of `devops config show`.
- Choose the tier of each attempt from the ladder, and advance to the next tier after a provider error without incrementing the repair round counter.
- Read gateway tier health before a tier choice and skip a tier that the gateway reports unhealthy.
- Record the token cost of each completed step under the tier that served it in the record of the run.
- Add spec deltas to `roadmap-implement-step`, `config-commands` and `ai-spend-pricing`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-step`: The step chooses a tier per attempt from the ladder
- `config-commands`: devops config show prints the model tier ladder
- `ai-spend-pricing`: The run record keeps the token cost per tier

## Impact

- Code: `src/devops_cli/config/settings.py`, `src/devops_cli/commands/config.py`, `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/implement_run.py`
- Documents: `openspec/changes/3060-model-tier-ladder/proposal.md`, `openspec/changes/3060-model-tier-ladder/design.md`, `openspec/changes/3060-model-tier-ladder/tasks.md`, `openspec/changes/3060-model-tier-ladder/specs/roadmap-implement-step/spec.md`, `openspec/changes/3060-model-tier-ladder/specs/config-commands/spec.md`, `openspec/changes/3060-model-tier-ladder/specs/ai-spend-pricing/spec.md`
- Tests: `tests/config/test_settings.py`, `tests/commands/test_config_cmd.py`, `tests/roadmap/test_roadmap_implement_step.py`, `tests/roadmap/test_roadmap_implement_step_repair.py`, `tests/roadmap/test_roadmap_implement_records.py`

## Feasibility

- The probe confirms the cited path: `The path docs/adr/0005-review-findings-come-from-tools-not-models.md is a file of the staging commit.` The issue cites only that ADR as its source, and it exists.
- `list_files` of `src/devops_cli/roadmap` showed `implement_step.py`, `implement_run.py` and `implement.py`, so the step executor that the issue asks to change exists. `list_files` of `tests/roadmap` showed `test_roadmap_implement_step.py` and `test_roadmap_implement_step_repair.py`, so the repair round has a test module to extend.
- `list_files` of `tests/roadmap` showed no `test_implement_step.py`; the module is `tests/roadmap/test_roadmap_implement_step.py`. `list_files` of `src/devops_cli/roadmap` showed no `trace.py`, so the per-tier cost record goes into the existing run record of `src/devops_cli/roadmap/implement_run.py`.
- The first checks that the implementation runs against the real system are `uv run devops ci test tests/commands/test_config_cmd.py` for the config surface and `uv run devops ci test tests/roadmap/test_roadmap_implement_step.py` for the step executor. Both are offline tests that double the process edges.

## Existing Tool Considered

LiteLLM (BerriAI/litellm) covers fallback routing between model deployments and reports the health of each deployment. It covers no per-step-class tier ladder, no skip of an unhealthy tier before each choice, and no per-tier token cost per roadmap item. The change builds that ladder on top of the existing model routing of `src/devops_cli/ai/gateway.py`; the cost is the tokens to build, keep and fix the config schema, the tier-advancing retry, the health read and the per-tier cost record. The change deletes no internal code.
