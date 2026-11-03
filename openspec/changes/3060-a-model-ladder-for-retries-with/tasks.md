# Tasks

## 1. Add the ladder setting and validate against hosted models

Reads: `src/devops_cli/config/settings.py`, `SECURITY.md`. Changes: `src/devops_cli/config/settings.py`, `tests/config/test_settings.py`.

- [x] 1.1 Add a failing test that `roadmap.implement.ladder` defaults to local tiers only, rejects hosted model names, and verify that `uv run devops ci test tests/config/test_settings.py` fails on the base
- [x] 1.2 Add the `ladder` field to `RoadmapImplementConfig`, default it to the local `devops-coder` group of each class, validate tier names against hosted models, and verify that `uv run devops ci test tests/config/test_settings.py` passes
- [x] 1.3 Update `docs/CONFIGURATION.md`, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 2. Show the ladder in config show

Reads: `src/devops_cli/commands/config.py`, `src/devops_cli/config/settings.py`. Changes: `src/devops_cli/commands/config.py`, `tests/commands/test_config_cmd.py`.

- [x] 2.1 Add a failing test that `devops config show` prints each step class and its tier list, and verify that `uv run devops ci test tests/commands/test_config_cmd.py` fails on the base
- [x] 2.2 Print the ladder mapping in `devops config show` output, and verify that `uv run devops ci test tests/commands/test_config_cmd.py` passes
- [x] 2.3 Update `docs/commands/config.md`, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 3. Handle tier change in failure taxonomy and stop comments

Reads: `src/devops_cli/roadmap/failure.py`. Changes: `src/devops_cli/roadmap/failure.py`, `tests/roadmap/test_roadmap_failure.py`.

- [x] 3.1 Add a failing test that `left_action` and `failure_lines` record `FailureAction.CHANGE_TIER` as an action taken, and verify that `uv run devops ci test tests/roadmap/test_roadmap_failure.py` fails on the base
- [x] 3.2 Update `failure_lines` to record `FailureAction.CHANGE_TIER` as the action taken when tier changes occurred, and verify that `uv run devops ci test tests/roadmap/test_roadmap_failure.py` passes
- [x] 3.3 Update `docs/roadmap/implement.md`, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 4. Read gateway tier health before choosing a tier

Reads: `src/devops_cli/ai/gateway.py`. Changes: `src/devops_cli/ai/gateway.py`, `tests/ai/test_ai_gateway_probes.py`.

- [x] 4.1 Add a failing test that queries tier health and skips an unhealthy tier, and verify that `uv run devops ci test tests/ai/test_ai_gateway_probes.py` fails on the base
- [x] 4.2 Implement tier health probing in `GatewayRouter`, and verify that `uv run devops ci test tests/ai/test_ai_gateway_probes.py` passes
- [x] 4.3 Update `docs/roadmap/implement.md`, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 5. Choose tier per attempt and record token cost per tier in run record

Reads: `src/devops_cli/commands/roadmap.py`, `src/devops_cli/ai/client/factory.py`, `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/failure.py`. Changes: `src/devops_cli/commands/roadmap.py`, `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/implement_run.py`, `tests/roadmap/test_roadmap_implement_step.py`, `tests/roadmap/test_roadmap_implement_records.py`.

- [x] 5.1 Add a failing test where tier 1 encounters `change_tier`, tier 2 succeeds, and the record names both tiers, and verify that `uv run devops ci test tests/roadmap/test_roadmap_implement_step.py` fails on the base
- [x] 5.2 Select the tier per attempt, advance on `change_tier` and on a provider error, add `tier`, `tiers` and `tier_spend` to `StepOutcome`, and itemize the spend under `tiers` in `implement.spend`, and verify that `uv run devops ci test tests/roadmap/test_roadmap_implement_step.py` passes
- [x] 5.3 Update `docs/roadmap/implement.md`, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Criteria

- A replay with a provider error on tier 1 succeeds on tier 2 and the trace names both.: group 5
- The ladder is a setting and `devops config show` prints it.: group 2
- The token cost per tier is recorded per item.: group 5
- No hosted-provider call happens unless the setting names one.: group 1

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
