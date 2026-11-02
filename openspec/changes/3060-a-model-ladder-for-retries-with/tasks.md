# Tasks

## 1. Add the ladder setting

Reads: `src/devops_cli/config/settings.py`. Changes: `src/devops_cli/config/settings.py`, `tests/config/test_settings.py`.

- [ ] 1.1 Add a failing test that the ladder maps each step class to an ordered tier list and that the default names only local tiers, and verify that `uv run devops ci test tests/config/test_settings.py` fails on the base
- [ ] 1.2 Add the ladder field to the settings, validate each tier name, and default it to local tiers only, and verify that `uv run devops ci test tests/config/test_settings.py` passes
- [ ] 1.3 docs/CONFIGURATION.md, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 2. Show the ladder in config show

Reads: `src/devops_cli/commands/config.py`, `src/devops_cli/config/settings.py`. Changes: `src/devops_cli/commands/config.py`, `tests/commands/test_config_cmd.py`.

- [ ] 2.1 Add a failing test that `devops config show` prints each step class and the tier of each attempt, and verify that `uv run devops ci test tests/commands/test_config_cmd.py` fails on the base
- [ ] 2.2 Print the ladder in the config show output, and verify that `uv run devops ci test tests/commands/test_config_cmd.py` passes
- [ ] 2.3 docs/commands/config.md, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 3. Choose the tier per attempt and move on a provider error

Reads: `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/implement_run.py`. Changes: `src/devops_cli/roadmap/implement_step.py`, `tests/roadmap/test_roadmap_implement_step.py`.

- [ ] 3.1 Add a failing replay test where tier 1 returns a provider error, tier 2 succeeds, and the run record names both tiers, and verify that `uv run devops ci test tests/roadmap/test_roadmap_implement_step.py` fails on the base
- [ ] 3.2 Pick the tier of each attempt from the ladder, advance on a provider error, and leave the repair round counter unchanged, and verify that `uv run devops ci test tests/roadmap/test_roadmap_implement_step.py` passes
- [ ] 3.3 docs/roadmap/implement.md, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 4. Read gateway tier health before choosing a tier

Reads: `src/devops_cli/ai/gateway.py`, `src/devops_cli/roadmap/implement_step.py`. Changes: `src/devops_cli/roadmap/implement_step.py`, `tests/roadmap/test_roadmap_implement_step_repair.py`.

- [ ] 4.1 Add a failing test that a tier the gateway reports unhealthy is skipped for the next healthy tier, and verify that `uv run devops ci test tests/roadmap/test_roadmap_implement_step_repair.py` fails on the base
- [ ] 4.2 Read the gateway tier health before a choice and skip an unhealthy tier, and verify that `uv run devops ci test tests/roadmap/test_roadmap_implement_step_repair.py` passes
- [ ] 4.3 docs/roadmap/implement.md, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 5. Record token cost per tier in the run record

Reads: `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/roadmap/implement_step.py`. Changes: `src/devops_cli/roadmap/implement_run.py`, `tests/roadmap/test_roadmap_implement_records.py`.

- [ ] 5.1 Add a failing test that a completed step records its token count under the tier that served it, and verify that `uv run devops ci test tests/roadmap/test_roadmap_implement_records.py` fails on the base
- [ ] 5.2 Record the tier and the token count of each completed step in the record of the run, and verify that `uv run devops ci test tests/roadmap/test_roadmap_implement_records.py` passes
- [ ] 5.3 docs/roadmap/implement.md, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 6. Write the change documents

Reads: `openspec/specs/roadmap-implement-step/spec.md`, `openspec/specs/config-commands/spec.md`, `openspec/specs/ai-spend-pricing/spec.md`. Changes: `openspec/changes/3060-model-tier-ladder/proposal.md` (new), `openspec/changes/3060-model-tier-ladder/design.md` (new), `openspec/changes/3060-model-tier-ladder/tasks.md` (new), `openspec/changes/3060-model-tier-ladder/specs/roadmap-implement-step/spec.md` (new), `openspec/changes/3060-model-tier-ladder/specs/config-commands/spec.md` (new), `openspec/changes/3060-model-tier-ladder/specs/ai-spend-pricing/spec.md` (new).

- [ ] 6.1 Write the proposal, the design, the tasks and the spec deltas of the change, and verify that `uv run devops openspec check` passes
- [ ] 6.2 openspec/changes/3060-model-tier-ladder/proposal.md, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Criteria

- A replay with a provider error on tier 1 succeeds on tier 2 and the trace names both.: group 3
- The ladder is a setting and `devops config show` prints it.: group 2
- The token cost per tier is recorded per item.: group 5
- No hosted-provider call happens unless the setting names one.: group 1

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
